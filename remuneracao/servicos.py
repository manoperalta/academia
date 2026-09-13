"""Apuracao de comissao com memoria de calculo e conferencia (RF-RED-017)."""

from __future__ import annotations

import hashlib
from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from remuneracao.models import (
    ApuracaoDeComissao,
    ItemDeComissao,
    RegraDeComissao,
    SituacaoDeApuracao,
    TipoDeComissao,
)

ZERO = Decimal("0.00")


class ErroDeRemuneracao(Exception):
    """Operacao recusada (sem regra, periodo invalido, sequencia errada)."""


def _arredonda(valor) -> Decimal:
    return Decimal(valor or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def competencia(referencia: date | None = None) -> tuple[date, date]:
    """Primeiro e ultimo dia do mes da data informada."""
    referencia = referencia or timezone.localdate()
    return referencia.replace(day=1), referencia.replace(
        day=monthrange(referencia.year, referencia.month)[1]
    )


def regra_para(professor, unidade=None, referencia: date | None = None) -> RegraDeComissao | None:
    """Regra do professor > regra da unidade > regra geral da rede."""
    referencia = referencia or timezone.localdate()
    consulta = RegraDeComissao.objects.filter(rede=professor.rede).order_by("-criado_em")
    for alvo in (
        {"professor": professor},
        {"professor__isnull": True, "unidade": unidade} if unidade else None,
        {"professor__isnull": True, "unidade__isnull": True},
    ):
        if alvo is None:
            continue
        for regra in consulta.filter(**alvo):
            if regra.vale_em(referencia):
                return regra
    return None


def alunos_ativos(unidade) -> int:
    from usuarios.models import Usuario

    return Usuario.todos.filter(unidade=unidade, status_user="Ativo").count()


def receita_recebida(unidade, inicio: date, fim: date) -> Decimal:
    from django.db.models import Sum

    from financeiro.models import Pagamento

    total = Pagamento.objects.filter(
        unidade=unidade, status="pago", data_pagamento__gte=inicio, data_pagamento__lte=fim
    ).aggregate(total=Sum("valor_pago"))["total"]
    return _arredonda(total)


def aulas_dadas(professor, unidade, inicio: date, fim: date) -> tuple[int, str]:
    """Conta aulas do professor no periodo quando a agenda permite; diz a fonte usada."""
    from django.apps import apps

    try:
        agendamento = apps.get_model("agendamento", "Agendamento")
        painel = apps.get_model("painel", "Painel")
    except LookupError:
        return 0, "agenda indisponivel neste cliente"
    campos_do_painel = {campo.name for campo in painel._meta.get_fields()}
    if "professor" not in campos_do_painel:
        return 0, "painel sem professor vinculado (comissao por aula nao apuravel)"
    campos = {campo.name for campo in agendamento._meta.get_fields()}
    campo_data = next(
        (
            nome
            for nome in ("data_agendamento", "data", "data_inicio", "criado_em")
            if nome in campos
        ),
        None,
    )
    if campo_data is None:
        return 0, "agendamento sem campo de data"
    filtro = {
        f"{campo_data}__gte": inicio,
        f"{campo_data}__lte": fim,
        "painel__professor": professor,
    }
    if "unidade" in campos and unidade is not None:
        filtro["unidade"] = unidade
    if "status" in campos:
        filtro["status__in"] = ["concluido", "presente", "realizado", "ativo"]
    total = agendamento.objects.filter(**filtro).count()
    return total, f"{total} aula(s) pela agenda"


def calcular_apuracao(professor, unidade, inicio: date, fim: date) -> dict:
    """Calcula (sem gravar) a comissao do professor no periodo, linha a linha."""
    if fim < inicio:
        raise ErroDeRemuneracao("periodo invalido")
    regra = regra_para(professor, unidade, fim)
    if regra is None:
        raise ErroDeRemuneracao(f"sem regra de comissao para {professor} em {fim:%m/%Y}")

    linhas: list[dict] = []
    base = ZERO
    if regra.tipo == TipoDeComissao.POR_AULA:
        quantidade, fonte = aulas_dadas(professor, unidade, inicio, fim)
        base = _arredonda(quantidade)
        valor = _arredonda(base * regra.valor)
        linhas.append(
            {
                "tipo": "por_aula",
                "descricao": f"Comissao por aula ({fonte})",
                "base": base,
                "percentual": ZERO,
                "valor": valor,
            }
        )
    elif regra.tipo == TipoDeComissao.POR_ALUNO:
        quantidade = alunos_ativos(unidade)
        base = _arredonda(quantidade)
        valor = _arredonda(base * regra.valor)
        linhas.append(
            {
                "tipo": "por_aluno",
                "descricao": "Alunos ativos na unidade",
                "base": base,
                "percentual": ZERO,
                "valor": valor,
            }
        )
    elif regra.tipo == TipoDeComissao.PERCENTUAL:
        base = receita_recebida(unidade, inicio, fim)
        valor = _arredonda(base * regra.percentual / Decimal("100"))
        linhas.append(
            {
                "tipo": "percentual",
                "descricao": "Percentual do recebido na unidade",
                "base": base,
                "percentual": regra.percentual,
                "valor": valor,
            }
        )
    else:
        base = regra.valor
        valor = _arredonda(regra.valor)
        linhas.append(
            {
                "tipo": "fixo",
                "descricao": "Valor fixo no periodo",
                "base": base,
                "percentual": ZERO,
                "valor": valor,
            }
        )

    total = sum((linha["valor"] for linha in linhas), ZERO)
    piso_aplicado = teto_aplicado = False
    if regra.piso_mensal and total < regra.piso_mensal:
        linhas.append(
            {
                "tipo": "piso",
                "descricao": "Complemento ate o piso mensal",
                "base": regra.piso_mensal,
                "percentual": ZERO,
                "valor": _arredonda(regra.piso_mensal - total),
            }
        )
        total = _arredonda(regra.piso_mensal)
        piso_aplicado = True
    if regra.teto_mensal and total > regra.teto_mensal:
        linhas.append(
            {
                "tipo": "teto",
                "descricao": "Ajuste ate o teto mensal",
                "base": regra.teto_mensal,
                "percentual": ZERO,
                "valor": _arredonda(regra.teto_mensal - total),
            }
        )
        total = _arredonda(regra.teto_mensal)
        teto_aplicado = True

    resumo = {
        "professor": professor.pk,
        "unidade": getattr(unidade, "pk", None),
        "inicio": str(inicio),
        "fim": str(fim),
        "regra": regra.pk,
        "tipo": regra.tipo,
        "total": str(total),
        "piso_aplicado": piso_aplicado,
        "teto_aplicado": teto_aplicado,
        "linhas": [
            {
                **linha,
                "base": str(linha["base"]),
                "percentual": str(linha["percentual"]),
                "valor": str(linha["valor"]),
            }
            for linha in linhas
        ],
    }
    resumo["hash"] = hashlib.sha256(
        "|".join(
            [str(resumo["professor"]), str(resumo["unidade"]), str(inicio), str(fim), str(total)]
            + [str(linha["valor"]) for linha in linhas]
        ).encode("utf-8")
    ).hexdigest()
    return {
        "linhas": linhas,
        "total": total,
        "base_de_calculo": base,
        "regra": regra,
        "piso_aplicado": piso_aplicado,
        "teto_aplicado": teto_aplicado,
        "resumo": resumo,
        "hash": resumo["hash"],
    }


def emitir_apuracao(
    professor, unidade, inicio: date, fim: date, usuario=None, forcar: bool = False
) -> ApuracaoDeComissao:
    """Cria (ou reaproveita) a apuracao do periodo; idempotente por professor+unidade+periodo."""
    existente = ApuracaoDeComissao.objects.filter(
        professor=professor, unidade=unidade, inicio=inicio, fim=fim
    ).first()
    if existente is not None:
        if existente.situacao == SituacaoDeApuracao.PAGO:
            raise ErroDeRemuneracao("apuracao ja paga nao pode ser recalculada")
        if existente.situacao == SituacaoDeApuracao.EMITIDO and not forcar:
            return existente
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    apuracao = existente or ApuracaoDeComissao(
        professor=professor, unidade=unidade, inicio=inicio, fim=fim
    )
    apuracao.rede = professor.rede
    apuracao.base_de_calculo = calculo["base_de_calculo"]
    apuracao.valor_devido = calculo["total"]
    apuracao.piso_aplicado = calculo["piso_aplicado"]
    apuracao.teto_aplicado = calculo["teto_aplicado"]
    apuracao.memoria = calculo["resumo"]["linhas"]
    apuracao.hash_do_calculo = calculo["hash"]
    apuracao.situacao = SituacaoDeApuracao.EMITIDO
    apuracao.emitido_em = timezone.now()
    apuracao.save()
    apuracao.itens.all().delete()
    ItemDeComissao.objects.bulk_create(
        [
            ItemDeComissao(
                apuracao=apuracao,
                ordem=ordem,
                **{
                    **linha,
                    "base": Decimal(linha["base"]),
                    "percentual": Decimal(linha["percentual"]),
                    "valor": Decimal(linha["valor"]),
                },
            )
            for ordem, linha in enumerate(calculo["linhas"], start=1)
        ]
    )
    if usuario is not None:
        from api.auditoria import registrar

        registrar(
            "emitir",
            "apuracao_de_comissao",
            entidade_id=apuracao.pk,
            descricao=f"Comissao de {professor} emitida ({inicio:%m/%Y})",
        )
    return apuracao


def conferir_apuracao(apuracao: ApuracaoDeComissao) -> dict:
    """Recalcula e compara item a item (o numero precisa ser reproduzivel)."""
    calculo = calcular_apuracao(apuracao.professor, apuracao.unidade, apuracao.inicio, apuracao.fim)
    divergencias = []
    if calculo["total"] != apuracao.valor_devido:
        divergencias.append(
            {
                "campo": "valor_devido",
                "gravado": str(apuracao.valor_devido),
                "recalculado": str(calculo["total"]),
            }
        )
    for ordem, linha in enumerate(calculo["linhas"], start=1):
        item = apuracao.itens.filter(ordem=ordem).first()
        if item is None:
            divergencias.append(
                {"campo": f"item {ordem}", "gravado": None, "recalculado": str(linha["valor"])}
            )
        elif item.valor != linha["valor"]:
            divergencias.append(
                {
                    "campo": f"item {ordem}",
                    "gravado": str(item.valor),
                    "recalculado": str(linha["valor"]),
                }
            )
    return {
        "ok": not divergencias,
        "divergencias": divergencias,
        "mesmo_numero": calculo["hash"] == apuracao.hash_do_calculo,
        "hash_atual": calculo["hash"],
        "hash_gravado": apuracao.hash_do_calculo,
    }


def apurar_competencia(
    rede, referencia: date | None = None, usuario=None, forcar: bool = False
) -> dict:
    """Apura a comissao de todos os professores ativos, por unidade (rateio)."""
    from professores.models import Professor

    referencia = referencia or timezone.localdate()
    inicio, fim = competencia(referencia)
    emitidas: list[dict] = []
    erros: list[dict] = []
    for professor in Professor.todos.filter(rede=rede, status_prof="Ativo"):
        unidades = (
            [professor.unidade]
            if getattr(professor, "unidade_id", None)
            else list(
                __import__("core.models", fromlist=["Unidade"]).Unidade.objects.filter(rede=rede)
            )
        )
        for unidade in unidades:
            try:
                apuracao = emitir_apuracao(professor, unidade, inicio, fim, usuario, forcar=forcar)
            except ErroDeRemuneracao as erro:
                erros.append(
                    {
                        "professor": professor.nome,
                        "unidade": getattr(unidade, "nome", None),
                        "erro": str(erro),
                    }
                )
                continue
            emitidas.append(
                {
                    "professor": professor.nome,
                    "unidade": getattr(unidade, "nome", None),
                    "valor": str(apuracao.valor_devido),
                    "situacao": apuracao.situacao,
                }
            )
    total = sum((Decimal(item["valor"]) for item in emitidas), ZERO)
    return {"inicio": inicio, "fim": fim, "emitidas": emitidas, "erros": erros, "total": total}


def marcar_paga(apuracao: ApuracaoDeComissao, valor=None, usuario=None) -> ApuracaoDeComissao:
    valor = _arredonda(valor if valor is not None else apuracao.saldo)
    apuracao.valor_pago = _arredonda((apuracao.valor_pago or ZERO) + valor)
    if apuracao.valor_pago >= apuracao.valor_devido:
        apuracao.situacao = SituacaoDeApuracao.PAGO
        apuracao.pago_em = timezone.now()
    apuracao.save(update_fields=["valor_pago", "situacao", "pago_em"])
    return apuracao


def extrato_do_professor(professor, limite: int = 12) -> dict:
    """O que o proprio professor ve: apuracoes, total do ano e pendencias."""
    apuracoes = ApuracaoDeComissao.objects.filter(professor=professor).order_by("-inicio")[:limite]
    pago = sum((item.valor_pago or ZERO for item in apuracoes), ZERO)
    devido = sum((item.valor_devido or ZERO for item in apuracoes), ZERO)
    return {
        "apuracoes": apuracoes,
        "total_devido": _arredonda(devido),
        "total_pago": _arredonda(pago),
        "saldo": _arredonda(devido - pago),
    }
