"""Servicos da rede: repasse, comparativo, metas, governanca, onboarding e transferencias."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import Rede, Unidade
from financeiro.models import Despesa, Pagamento
from usuarios.models import Usuario

from rede.models import (
    Comunicado, DistribuicaoDeCatalogo, ImplantacaoDeUnidade, ItemDeRepasse, Meta, PoliticaDaRede,
    RegraDeRepasse, Repasse, SolicitacaoDeAprovacao, TemplateDeUnidade, TransferenciaDeAluno,
)

ZERO = Decimal("0.00")
CENTAVO = Decimal("0.01")
TERMOS_DE_PARCEIROS = ("wellhub", "gympass", "totalpass", "classpass")


class ErroDeRede(Exception):
    """Operacao recusada pela politica da rede (mensagem pronta para o usuario)."""


def _dinheiro(valor) -> Decimal:
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def politica(rede) -> PoliticaDaRede:
    return PoliticaDaRede.da_rede(rede)


# ------------------------------------------------------------------ periodos
def periodo_do_mes(referencia: date | None = None) -> tuple[date, date]:
    referencia = referencia or timezone.localdate()
    inicio = referencia.replace(day=1)
    proximo = (inicio + timedelta(days=32)).replace(day=1)
    return inicio, proximo - timedelta(days=1)


# ------------------------------------------------------------------ regra e politica
def regra_para(unidade: Unidade, referencia: date | None = None) -> RegraDeRepasse | None:
    """Regra da unidade; se nao houver, a padrao da rede (RF-RED-012)."""
    referencia = referencia or timezone.localdate()
    candidatas = (
        RegraDeRepasse.objects.filter(rede=unidade.rede, unidade=unidade, ativo=True)
        | RegraDeRepasse.objects.filter(rede=unidade.rede, unidade__isnull=True, ativo=True)
    ).distinct()
    vigentes = [regra for regra in candidatas if regra.vale_em(referencia)]
    if not vigentes:
        return None
    vigentes.sort(key=lambda regra: (regra.unidade_id is None, -regra.pk))  # da unidade primeiro
    return vigentes[0]


def travas_vigentes(rede) -> dict:
    """Campos travados pela rede, com o motivo mostrado na interface (RF-RED-014)."""
    politica_da_rede = politica(rede)
    return {
        "planos_e_precos": politica_da_rede.trava_planos_e_precos,
        "politica_de_desconto": politica_da_rede.trava_politica_de_desconto,
        "regua_de_cobranca": politica_da_rede.trava_regua_de_cobranca,
        "contratos": politica_da_rede.trava_contratos,
        "cancelamento": politica_da_rede.trava_cancelamento,
        "templates_de_mensagem": politica_da_rede.trava_templates_de_mensagem,
    }


def validar_desconto(unidade: Unidade, percentual) -> dict:
    """Dentro do teto? Se passar, precisa de aprovacao da rede (RF-RED-018)."""
    politica_da_rede = politica(unidade.rede)
    percentual = Decimal(str(percentual or 0))
    if not politica_da_rede.trava_politica_de_desconto or percentual <= politica_da_rede.teto_de_desconto:
        return {"permitido": True, "exige_aprovacao": False, "teto": politica_da_rede.teto_de_desconto}
    return {
        "permitido": False,
        "exige_aprovacao": True,
        "teto": politica_da_rede.teto_de_desconto,
        "mensagem": (
            f"O teto de desconto da rede e {politica_da_rede.teto_de_desconto}%. "
            "Acima disso, e preciso aprovar com a rede."
        ),
    }


# ------------------------------------------------------------------ repasse
def receita_do_periodo(unidade: Unidade, inicio: date, fim: date) -> dict:
    """Receita da unidade no periodo, com o detalhamento que entra na memoria."""
    base = Pagamento.objects.filter(
        rede=unidade.rede,
        data_pagamento__gte=inicio,
        data_pagamento__lte=fim,
    )
    por_unidade = base.filter(Q(unidade=unidade) | Q(unidade__isnull=True))
    pagos = por_unidade.filter(status="pago")
    bruta = _dinheiro(pagos.aggregate(total=Sum("valor_pago"))["total"])
    devolvidos = _dinheiro(
        por_unidade.filter(status__in=["devolvido", "cancelado"]).aggregate(total=Sum("valor_pago"))["total"]
    )
    parceiros = ZERO
    detalhe_por_plano = list(
        pagos.values("plano__nome").annotate(total=Sum("valor_pago"), quantidade=Count("id")).order_by("-total")
    )
    for linha in detalhe_por_plano:
        nome = (linha["plano__nome"] or "").lower()
        if any(termo in nome for termo in TERMOS_DE_PARCEIROS):
            parceiros += _dinheiro(linha["total"])
    return {
        "receita_bruta": bruta,
        "devolucoes": devolvidos,
        "planos_de_parceiros": _dinheiro(parceiros),
        "pagamentos": pagos.count(),
        "por_plano": detalhe_por_plano,
        "alunos_ativos": Usuario.todos.filter(
            rede=unidade.rede, unidade=unidade, status_user="Ativo"
        ).count(),
    }


def calcular_repasse(unidade: Unidade, inicio: date, fim: date) -> dict:
    """Calcula o repasse SEM gravar: base, exclusoes, aliquotas e memoria linha a linha."""
    regra = regra_para(unidade, referencia=fim)
    if regra is None:
        raise ErroDeRede(
            f"Nao ha regra de repasse vigente para {unidade.nome}. Defina a regra da unidade "
            "ou a regra padrao da rede antes de calcular."
        )
    receita = receita_do_periodo(unidade, inicio, fim)
    linhas: list[dict] = []
    ordem = 1

    linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.RECEITA,
                   "descricao": f"Receita recebida no periodo ({receita['pagamentos']} pagamento(s))",
                   "base": receita["receita_bruta"], "percentual": ZERO,
                   "valor": receita["receita_bruta"], "referencia": ""})
    ordem += 1

    exclusoes = ZERO
    if regra.base == RegraDeRepasse.Base.LIQUIDO:
        if regra.excluir_estornos and receita["devolucoes"]:
            exclusoes += receita["devolucoes"]
            linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.EXCLUSAO,
                           "descricao": "Estornos e devolucoes", "base": receita["devolucoes"],
                           "percentual": ZERO, "valor": -receita["devolucoes"], "referencia": ""})
            ordem += 1
        if regra.excluir_taxas_de_gateway and regra.percentual_de_taxas_de_gateway:
            taxa = _dinheiro(receita["receita_bruta"] * regra.percentual_de_taxas_de_gateway / 100)
            exclusoes += taxa
            linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.EXCLUSAO,
                           "descricao": f"Taxas de gateway ({regra.percentual_de_taxas_de_gateway}%)",
                           "base": receita["receita_bruta"],
                           "percentual": regra.percentual_de_taxas_de_gateway, "valor": -taxa,
                           "referencia": ""})
            ordem += 1
        if regra.excluir_impostos and regra.percentual_de_impostos:
            impostos = _dinheiro(receita["receita_bruta"] * regra.percentual_de_impostos / 100)
            exclusoes += impostos
            linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.EXCLUSAO,
                           "descricao": f"Impostos sobre a receita ({regra.percentual_de_impostos}%)",
                           "base": receita["receita_bruta"],
                           "percentual": regra.percentual_de_impostos, "valor": -impostos,
                           "referencia": ""})
            ordem += 1
        if regra.excluir_planos_de_parceiros and receita["planos_de_parceiros"]:
            exclusoes += receita["planos_de_parceiros"]
            linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.EXCLUSAO,
                           "descricao": "Planos de parceiros (Wellhub/TotalPass e similares)",
                           "base": receita["planos_de_parceiros"], "percentual": ZERO,
                           "valor": -receita["planos_de_parceiros"], "referencia": ""})
            ordem += 1

    receita_liquida = _dinheiro(receita["receita_bruta"] - exclusoes)
    base_de_calculo = receita_liquida if regra.base == RegraDeRepasse.Base.LIQUIDO else receita["receita_bruta"]

    royalty = ZERO
    if regra.tipo in {RegraDeRepasse.Tipo.PERCENTUAL, RegraDeRepasse.Tipo.PERCENTUAL_MAIS_FIXO}:
        royalty = _dinheiro(base_de_calculo * (regra.percentual or 0) / 100)
        linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.ROYALTY,
                       "descricao": f"Royalty de {regra.percentual}% sobre a base ({regra.get_base_display()})",
                       "base": base_de_calculo, "percentual": regra.percentual, "valor": royalty,
                       "referencia": regra.get_tipo_display()})
        ordem += 1

    valor_fixo = ZERO
    if regra.tipo in {RegraDeRepasse.Tipo.FIXO, RegraDeRepasse.Tipo.PERCENTUAL_MAIS_FIXO}:
        valor_fixo = _dinheiro(regra.valor_fixo)
        linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.FIXO,
                       "descricao": "Valor fixo do periodo", "base": ZERO, "percentual": ZERO,
                       "valor": valor_fixo, "referencia": regra.get_tipo_display()})
        ordem += 1

    fundo = ZERO
    if regra.fundo_de_marketing:
        fundo = _dinheiro(base_de_calculo * regra.fundo_de_marketing / 100)
        linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.FUNDO,
                       "descricao": f"Fundo de marketing de {regra.fundo_de_marketing}%",
                       "base": base_de_calculo, "percentual": regra.fundo_de_marketing,
                       "valor": fundo, "referencia": ""})
        ordem += 1

    total = _dinheiro(royalty + fundo + valor_fixo)
    piso_aplicado = False
    if regra.piso_minimo and total < regra.piso_minimo:
        diferenca = _dinheiro(regra.piso_minimo - total)
        linhas.append({"ordem": ordem, "tipo": ItemDeRepasse.Tipo.PISO,
                       "descricao": f"Ajuste ate o piso minimo de R$ {regra.piso_minimo}",
                       "base": total, "percentual": ZERO, "valor": diferenca,
                       "referencia": "piso minimo"})
        total = _dinheiro(regra.piso_minimo)
        piso_aplicado = True

    vencimento_base = fim + timedelta(days=max(1, regra.dia_de_vencimento))
    return {
        "unidade": unidade,
        "inicio": inicio,
        "fim": fim,
        "regra": regra,
        "base": regra.base,
        "receita_bruta": receita["receita_bruta"],
        "exclusoes": _dinheiro(exclusoes),
        "receita_liquida": receita_liquida,
        "base_de_calculo": base_de_calculo,
        "percentual": regra.percentual or ZERO,
        "fundo_de_marketing": regra.fundo_de_marketing or ZERO,
        "royalty": royalty,
        "fundo": fundo,
        "valor_fixo": valor_fixo,
        "valor_devido": total,
        "piso_aplicado": piso_aplicado,
        "vencimento": vencimento_base,
        "linhas": linhas,
        "receita_detalhe": {
            "pagamentos": receita["pagamentos"],
            "alunos_ativos": receita["alunos_ativos"],
            "por_plano": [
                {"plano": linha["plano__nome"] or "sem plano",
                 "total": str(_dinheiro(linha["total"])), "quantidade": linha["quantidade"]}
                for linha in receita["por_plano"]
            ],
        },
    }


@transaction.atomic
def emitir_repasse(unidade: Unidade, inicio: date, fim: date, usuario=None, forcar: bool = False) -> Repasse:
    """Emite (ou devolve) o repasse do periodo. Rodar duas vezes nao duplica (RF-RED-012)."""
    existente = Repasse.objects.filter(unidade=unidade, inicio=inicio, fim=fim).first()
    if existente is not None and not forcar:
        return existente
    calculo = calcular_repasse(unidade, inicio, fim)
    repasse = existente or Repasse(unidade=unidade, rede=unidade.rede, inicio=inicio, fim=fim)
    repasse.rede = unidade.rede
    repasse.base = calculo["base"]
    repasse.receita_bruta = calculo["receita_bruta"]
    repasse.exclusoes = calculo["exclusoes"]
    repasse.receita_liquida = calculo["receita_liquida"]
    repasse.base_de_calculo = calculo["base_de_calculo"]
    repasse.percentual = calculo["percentual"]
    repasse.fundo_de_marketing = calculo["fundo_de_marketing"]
    repasse.valor_do_royalty = calculo["royalty"]
    repasse.valor_do_fundo = calculo["fundo"]
    repasse.valor_fixo = calculo["valor_fixo"]
    repasse.valor_devido = calculo["valor_devido"]
    repasse.piso_aplicado = calculo["piso_aplicado"]
    repasse.vencimento = calculo["vencimento"]
    repasse.situacao = Repasse.Situacao.EMITIDO
    repasse.emitido_em = timezone.now()
    repasse.memoria = {
        "linhas": [
            {"ordem": linha["ordem"], "tipo": linha["tipo"], "descricao": linha["descricao"],
             "base": str(linha["base"]), "percentual": str(linha["percentual"]),
             "valor": str(linha["valor"]), "referencia": linha["referencia"]}
            for linha in calculo["linhas"]
        ],
        "receita": calculo["receita_detalhe"],
        "regra": {"tipo": calculo["regra"].get_tipo_display(), "base": calculo["regra"].get_base_display(),
                  "percentual": str(calculo["regra"].percentual),
                  "fundo": str(calculo["regra"].fundo_de_marketing),
                  "piso": str(calculo["regra"].piso_minimo)},
    }
    repasse.save()
    repasse.itens.all().delete()
    ItemDeRepasse.objects.bulk_create([
        ItemDeRepasse(repasse=repasse, ordem=linha["ordem"], tipo=linha["tipo"],
                      descricao=linha["descricao"][:200], base=linha["base"],
                      percentual=linha["percentual"], valor=linha["valor"],
                      referencia=linha["referencia"][:120])
        for linha in calculo["linhas"]
    ])
    repasse.hash_do_calculo = repasse.recalcular_hash()
    repasse.save(update_fields=["hash_do_calculo", "atualizado_em"])
    from api.auditoria import registrar

    registrar("emitir", "repasse", entidade_id=repasse.pk,
              descricao=f"Repasse de {unidade.nome} {inicio:%m/%Y}: R$ {repasse.valor_devido}",
              request=None)
    return repasse


def conferir_repasse(repasse: Repasse) -> dict:
    """Recalcula e confere LINHA A LINHA com o que foi emitido (RF-RED-012)."""
    recalculado = calcular_repasse(repasse.unidade, repasse.inicio, repasse.fim)
    divergencias = []
    comparacoes = [
        ("Receita bruta", repasse.receita_bruta, recalculado["receita_bruta"]),
        ("Exclusoes", repasse.exclusoes, recalculado["exclusoes"]),
        ("Base de calculo", repasse.base_de_calculo, recalculado["base_de_calculo"]),
        ("Royalty", repasse.valor_do_royalty, recalculado["royalty"]),
        ("Fundo de marketing", repasse.valor_do_fundo, recalculado["fundo"]),
        ("Valor fixo", repasse.valor_fixo, recalculado["valor_fixo"]),
        ("Total devido", repasse.valor_devido, recalculado["valor_devido"]),
    ]
    for rotulo, gravado, novo in comparacoes:
        if _dinheiro(gravado) != _dinheiro(novo):
            divergencias.append({"linha": rotulo, "gravado": str(_dinheiro(gravado)),
                                 "recalculado": str(_dinheiro(novo))})

    linhas_gravadas = [
        (item.tipo, item.descricao, _dinheiro(item.valor)) for item in repasse.itens.all()
    ]
    linhas_novas = [
        (linha["tipo"], linha["descricao"], _dinheiro(linha["valor"])) for linha in recalculado["linhas"]
    ]
    for esperado, encontrado in zip(linhas_gravadas, linhas_novas, strict=False):
        if esperado != encontrado:
            divergencias.append({"linha": esperado[1], "gravado": str(esperado[2]),
                                 "recalculado": str(encontrado[2])})
    if len(linhas_gravadas) != len(linhas_novas):
        divergencias.append({"linha": "Quantidade de linhas da memoria",
                             "gravado": str(len(linhas_gravadas)),
                             "recalculado": str(len(linhas_novas))})

    hash_novo = repasse.recalcular_hash()
    return {
        "ok": not divergencias,
        "divergencias": divergencias,
        "hash_gravado": repasse.hash_do_calculo,
        "hash_recalculado": hash_novo,
        "mesmo_numero": not divergencias and hash_novo == repasse.hash_do_calculo,
        "recalculado": recalculado,
    }


def marcar_repasse_pago(repasse: Repasse, valor, usuario=None) -> Repasse:
    repasse.valor_pago = _dinheiro(valor)
    repasse.pago_em = timezone.now()
    repasse.situacao = (Repasse.Situacao.PAGO if repasse.saldo <= ZERO else Repasse.Situacao.EMITIDO)
    repasse.save(update_fields=["valor_pago", "pago_em", "situacao", "atualizado_em"])
    return repasse


def atualizar_atrasados(rede=None) -> int:
    """Marca como atrasado o que venceu e nao foi pago."""
    pendentes = Repasse.objects.filter(
        situacao__in=[Repasse.Situacao.EMITIDO, Repasse.Situacao.PREVISTO],
        vencimento__lt=timezone.localdate(),
    )
    if rede is not None:
        pendentes = pendentes.filter(rede=rede)
    return pendentes.update(situacao=Repasse.Situacao.ATRASADO)


def emitir_repasses_do_mes(rede=None, referencia: date | None = None) -> dict:
    """Emite o repasse do periodo para todas as unidades ativas (rotina mensal)."""
    inicio, fim = periodo_do_mes(referencia)
    unidades = Unidade.objects.filter(status="ativa")
    if rede is not None:
        unidades = unidades.filter(rede=rede)
    emitidos, erros = [], []
    for unidade in unidades:
        try:
            repasse = emitir_repasse(unidade, inicio, fim)
            emitidos.append({"unidade": unidade.nome, "valor": str(repasse.valor_devido),
                             "situacao": repasse.get_situacao_display()})
        except ErroDeRede as erro:
            erros.append({"unidade": unidade.nome, "erro": str(erro)})
    return {"inicio": inicio, "fim": fim, "emitidos": emitidos, "erros": erros,
            "total": str(_dinheiro(sum(Decimal(item["valor"]) for item in emitidos)))}


def relatorio_de_repasses(rede, inicio: date, fim: date) -> dict:
    repasses = Repasse.objects.filter(rede=rede, inicio__gte=inicio, fim__lte=fim).select_related("unidade")
    return {
        "repasses": repasses,
        "total_devido": _dinheiro(repasses.aggregate(total=Sum("valor_devido"))["total"]),
        "total_pago": _dinheiro(repasses.aggregate(total=Sum("valor_pago"))["total"]),
        "por_unidade": list(repasses.values("unidade__nome").annotate(
            devido=Sum("valor_devido"), pago=Sum("valor_pago")).order_by("-devido")),
        "atrasados": [repasse for repasse in repasses if repasse.atrasado],
    }


# ------------------------------------------------------------------ rede: comparativo e metas
def comparativo_entre_unidades(rede, inicio: date, fim: date) -> list[dict]:
    """Comparativo por unidade: receita, alunos, ticket, inadimplencia (RF-RED-009)."""
    unidades = Unidade.objects.filter(rede=rede).order_by("nome")
    linhas = []
    for unidade in unidades:
        pagamentos = Pagamento.objects.filter(
            rede=rede, data_pagamento__gte=inicio, data_pagamento__lte=fim,
            unidade=unidade,
        )
        recebido = _dinheiro(pagamentos.filter(status="pago").aggregate(total=Sum("valor_pago"))["total"])
        em_aberto = _dinheiro(pagamentos.filter(status__in=["pendente", "em_analise"]).aggregate(
            total=Sum("valor_pago"))["total"])
        alunos_ativos = Usuario.todos.filter(rede=rede, unidade=unidade, status_user="Ativo").count()
        alunos_novos = Usuario.todos.filter(rede=rede, unidade=unidade,
                                            data_create_user__date__gte=inicio,
                                            data_create_user__date__lte=fim).count()
        ticket = _dinheiro(recebido / alunos_ativos) if alunos_ativos else ZERO
        total_geral = recebido + em_aberto
        inadimplencia = _dinheiro(em_aberto / total_geral * 100) if total_geral else ZERO
        repasse = Repasse.objects.filter(unidade=unidade, inicio__gte=inicio, fim__lte=fim).first()
        linhas.append({
            "unidade": unidade,
            "tipo": unidade.get_tipo_display(),
            "status": unidade.get_status_display(),
            "recebido": recebido,
            "em_aberto": em_aberto,
            "alunos_ativos": alunos_ativos,
            "alunos_novos": alunos_novos,
            "ticket_medio": ticket,
            "inadimplencia": inadimplencia,
            "repasse": repasse.valor_devido if repasse else ZERO,
            "despesas": _dinheiro(Despesa.objects.filter(
                rede=rede, unidade=unidade, data__gte=inicio, data__lte=fim
            ).aggregate(total=Sum("valor"))["total"]),
        })
    ordenadas = sorted(linhas, key=lambda linha: linha["recebido"], reverse=True)
    for posicao, linha in enumerate(ordenadas, start=1):
        linha["posicao"] = posicao
    return ordenadas


def consolidado_da_rede(rede, inicio: date, fim: date) -> dict:
    """Consolidado financeiro da rede com o total e a evolucao (RF-RED-010)."""
    comparativo = comparativo_entre_unidades(rede, inicio, fim)
    total_recebido = _dinheiro(sum(linha["recebido"] for linha in comparativo))
    total_aberto = _dinheiro(sum(linha["em_aberto"] for linha in comparativo))
    total_despesas = _dinheiro(sum(linha["despesas"] for linha in comparativo))
    total_repasses = _dinheiro(sum(linha["repasse"] for linha in comparativo))
    por_mes = list(
        Pagamento.objects.filter(rede=rede, status="pago", data_pagamento__gte=inicio,
                                 data_pagamento__lte=fim)
        .values("data_pagamento__year", "data_pagamento__month")
        .annotate(total=Sum("valor_pago")).order_by("data_pagamento__year", "data_pagamento__month")
    )
    return {
        "inicio": inicio,
        "fim": fim,
        "unidades": len(comparativo),
        "recebido": total_recebido,
        "em_aberto": total_aberto,
        "despesas": total_despesas,
        "resultado": _dinheiro(total_recebido - total_despesas),
        "repasses": total_repasses,
        "alunos_ativos": sum(linha["alunos_ativos"] for linha in comparativo),
        "ticket_medio": _dinheiro(total_recebido / sum(linha["alunos_ativos"] for linha in comparativo))
        if sum(linha["alunos_ativos"] for linha in comparativo) else ZERO,
        "por_mes": por_mes,
        "comparativo": comparativo,
        "por_plano": list(
            Pagamento.objects.filter(rede=rede, status="pago", data_pagamento__gte=inicio,
                                     data_pagamento__lte=fim)
            .values("plano__nome").annotate(total=Sum("valor_pago")).order_by("-total")
        ),
    }


def calcular_realizado(meta: Meta) -> Decimal:
    """Quanto a meta ja realizou, conforme o indicador (RF-RED-008)."""
    unidades = Unidade.objects.filter(rede=meta.rede)
    if meta.unidade_id:
        unidades = unidades.filter(pk=meta.unidade_id)
    pagamentos = Pagamento.objects.filter(
        rede=meta.rede, unidade__in=unidades, data_pagamento__gte=meta.inicio,
        data_pagamento__lte=meta.fim,
    )
    if meta.indicador == Meta.Indicador.FATURAMENTO:
        return _dinheiro(pagamentos.filter(status="pago").aggregate(total=Sum("valor_pago"))["total"])
    if meta.indicador == Meta.Indicador.NOVAS_MATRICULAS:
        return Decimal(Usuario.todos.filter(
            rede=meta.rede, unidade__in=unidades, data_create_user__date__gte=meta.inicio,
            data_create_user__date__lte=meta.fim,
        ).count())
    if meta.indicador == Meta.Indicador.TICKET_MEDIO:
        recebido = _dinheiro(pagamentos.filter(status="pago").aggregate(total=Sum("valor_pago"))["total"])
        alunos = Usuario.todos.filter(rede=meta.rede, unidade__in=unidades, status_user="Ativo").count()
        return _dinheiro(recebido / alunos) if alunos else ZERO
    if meta.indicador == Meta.Indicador.RETENCAO:
        inicio_ativos = Usuario.todos.filter(
            rede=meta.rede, unidade__in=unidades, data_create_user__date__lte=meta.inicio
        ).count()
        hoje_ativos = Usuario.todos.filter(
            rede=meta.rede, unidade__in=unidades, status_user="Ativo", data_create_user__date__lte=meta.inicio
        ).count()
        return _dinheiro(Decimal(hoje_ativos) / inicio_ativos * 100) if inicio_ativos else ZERO
    return ZERO  # ocupacao depende de dados de turma que o cliente ainda nao tem


def atualizar_metas(rede) -> int:
    atualizadas = 0
    for meta in Meta.objects.filter(rede=rede):
        realizado = calcular_realizado(meta)
        if meta.realizado != realizado:
            meta.realizado = realizado
            meta.save(update_fields=["realizado", "atualizado_em"])
        atualizadas += 1
    return atualizadas


# ------------------------------------------------------------------ governanca, onboarding e transferencias
def distribuir_catalogo(rede, referencia: str, unidades, usuario=None) -> DistribuicaoDeCatalogo:
    """Distribui um conteudo da rede para as unidades escolhidas (RF-RED-006)."""
    from aulas.models import Aulas as Aula

    origem = Aula.todos.filter(rede=rede, pk=int(referencia)).first() if str(referencia).isdigit() else None
    resultado = {"copias": [], "erros": []}
    if origem is None:
        resultado["erros"].append("Aula de origem nao encontrada na rede.")
    else:
        for unidade in unidades:
            try:
                dados = {}
                for campo in origem._meta.concrete_fields:
                    if campo.name in {"id", "pk", "rede", "unidade"} or campo.primary_key:
                        continue
                    dados[campo.name] = None if campo.name == "arquivado_em" else getattr(origem, campo.name)
                destino = Aula.todos.create(rede=rede, unidade=unidade, **dados)
                resultado["copias"].append({"unidade": unidade.nome, "aula": str(destino.pk)})
            except Exception as erro:  # noqa: BLE001 - segue distribuindo e reporta
                resultado["erros"].append({"unidade": unidade.nome, "erro": str(erro)[:200]})
    distribuicao = DistribuicaoDeCatalogo.objects.create(
        rede=rede, referencia=str(referencia), unidades=[unidade.pk for unidade in unidades],
        resultado=resultado, criado_por=usuario if getattr(usuario, "pk", None) else None,
    )
    from api.auditoria import registrar

    registrar("distribuir", "catalogo", entidade_id=distribuicao.pk,
              descricao=f"Catalogo distribuido para {len(resultado['copias'])} unidade(s)")
    return distribuicao


@transaction.atomic
def aplicar_template(unidade: Unidade, template: TemplateDeUnidade | None, usuario=None) -> ImplantacaoDeUnidade:
    """Aplica o template de configuracao na unidade e cria o checklist (RF-RED-016)."""
    resultado = {"aplicado": [], "ignorado": []}
    configuracoes = (template.configuracoes if template else {}) or {}
    if configuracoes.get("branding"):
        unidade.sobrescrever_branding = bool(configuracoes["branding"].get("sobrescrever", False))
        unidade.save(update_fields=["sobrescrever_branding", "atualizado_em"])
        resultado["aplicado"].append("marca")
    for chave in ("planos", "grades", "mensagens", "usuarios_padrao"):
        if configuracoes.get(chave):
            resultado["aplicado"].append(chave)
        else:
            resultado["ignorado"].append(chave)
    implantacao, _ = ImplantacaoDeUnidade.objects.update_or_create(
        unidade=unidade, defaults={"template": template, "resultado": resultado},
    )
    from api.auditoria import registrar

    registrar("implantar", "unidade", entidade_id=unidade.pk,
              descricao=f"Template {template.nome if template else '(vazio)'} aplicado em {unidade.nome}")
    return implantacao


@transaction.atomic
def marcar_item_do_checklist(implantacao: ImplantacaoDeUnidade, item_id: int, concluido: bool = True):
    itens = list(implantacao.itens_concluidos or [])
    if concluido and item_id not in itens:
        itens.append(item_id)
    if not concluido and item_id in itens:
        itens.remove(item_id)
    implantacao.itens_concluidos = itens
    total = implantacao.template.itens.count() if implantacao.template else 0
    implantacao.concluida_em = timezone.now() if total and len(itens) >= total else None
    implantacao.save(update_fields=["itens_concluidos", "concluida_em"])
    return implantacao


@transaction.atomic
def transferir_alunos(alunos, destino: Unidade, motivo: str = "", usuario=None) -> dict:
    """Transferencia de alunos entre unidades, individual ou em lote (RF-RED-004/024)."""
    lote = uuid.uuid4().hex[:12]
    transferencias, erros = [], []
    for aluno in alunos:
        origem = aluno.unidade
        if origem is not None and origem.pk == destino.pk:
            erros.append({"aluno": aluno.nome, "erro": "ja esta nesta unidade"})
            continue
        if aluno.rede_id != destino.rede_id:
            erros.append({"aluno": aluno.nome, "erro": "aluno de outra rede"})
            continue
        aluno.unidade = destino
        aluno.save(update_fields=["unidade", "data_at_user"])
        transferencias.append(TransferenciaDeAluno.objects.create(
            rede=destino.rede, aluno=aluno, origem=origem, destino=destino, motivo=motivo[:200],
            autorizado_por=usuario if getattr(usuario, "pk", None) else None, lote=lote,
        ))
    from api.auditoria import registrar

    registrar("transferir", "aluno", entidade_id=destino.pk,
              descricao=f"{len(transferencias)} aluno(s) transferido(s) para {destino.nome} (lote {lote})")
    return {"lote": lote, "transferidos": len(transferencias), "erros": erros}


@transaction.atomic
def encerrar_unidade(unidade: Unidade, destino: Unidade | None, usuario=None) -> dict:
    """Encerra a unidade: bloqueia, transfere em lote e exporta (RF-RED-024)."""
    if destino is not None and destino.pk == unidade.pk:
        raise ErroDeRede("A unidade de destino precisa ser diferente da unidade encerrada.")
    alunos = list(Usuario.todos.filter(rede=unidade.rede, unidade=unidade))
    resultado = {"alunos": len(alunos), "transferidos": 0, "erros": [], "exportacao": ""}
    if destino is not None:
        movimento = transferir_alunos(alunos, destino, motivo=f"Encerramento de {unidade.nome}",
                                      usuario=usuario)
        resultado["transferidos"] = movimento["transferidos"]
        resultado["erros"] = movimento["erros"]
    unidade.status = "inativa"
    unidade.save(update_fields=["status", "atualizado_em"])
    registro = Comunicado.objects.create(
        rede=unidade.rede, unidade=None, publico=Comunicado.Publico.UNIDADES,
        titulo=f"Unidade {unidade.nome} encerrada", exige_confirmacao=False,
        mensagem=(
            f"A unidade {unidade.nome} foi encerrada. "
            + (f"{resultado['transferidos']} aluno(s) transferido(s) para {destino.nome}."
               if destino else "Os alunos ficaram sem unidade de destino.")
            + " Os dados financeiros permanecem retidos pelo prazo legal."
        ),
        criado_por=usuario if getattr(usuario, "pk", None) else None,
    )
    resultado["comunicado"] = registro.pk
    from api.auditoria import registrar

    registrar("encerrar", "unidade", entidade_id=unidade.pk,
              descricao=f"Unidade {unidade.nome} encerrada ({resultado['transferidos']} transferido(s))")
    return resultado


def comparar_grade(modelo, destino: Unidade) -> dict:
    """Copia a grade de horarios de uma unidade para outra (RF-RED-007)."""
    criados, erros = 0, []
    registros = list(modelo.todos.filter(rede=destino.rede))
    for registro in registros:
        origem_unidade = getattr(registro, "unidade", None)
        if origem_unidade is None or origem_unidade.pk == destino.pk:
            continue
        campos = {
            campo.name: getattr(registro, campo.name)
            for campo in registro._meta.get_fields()
            if campo.name not in {"id", "pk", "unidade", "rede"} and not campo.is_relation
        }
        try:
            modelo.todos.create(rede=destino.rede, unidade=destino, **campos)
            criados += 1
        except Exception as erro:  # noqa: BLE001
            erros.append(str(erro)[:200])
    return {"copiados": criados, "erros": erros}


def importar_multi_unidade(conteudo: bytes, rede, tipo: str = "alunos", atualizar: bool = False) -> dict:
    """Importacao com coluna de unidade e relatorio de conferencia por unidade (RF-RED-023)."""
    from gestao.importacao import analisar_aplicar_multiunidade

    return analisar_aplicar_multiunidade(conteudo, rede, tipo=tipo, atualizar_existentes=atualizar)
