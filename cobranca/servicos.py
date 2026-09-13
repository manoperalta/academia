"""Servicos da cobranca recorrente.

Duas regras que protegem o dinheiro da rede:

1. **Um pagamento por cobranca** — o retorno do banco pode chegar repetido (webhook reenviado); a
   segunda chegada nao gera segundo pagamento, so um evento a mais no historico.
2. **Nada de cobranca sem autorizacao ativa** — quem nao autorizou entra na regua de contato, nao
   no debito.

Sem PSP configurado o envio roda em **modo simulado**, declarado na tela e no proprio registro.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from cobranca.models import AutorizacaoDeDebito, CobrancaRecorrente, EventoDaCobranca

DIAS_DE_RECORRENCIA = 30
ETAPAS_DA_REGUA = {
    -3: "Sua mensalidade vence em 3 dias.",
    0: "Sua mensalidade vence hoje.",
    1: "Sua mensalidade venceu ontem.",
    5: "Sua mensalidade esta 5 dias em atraso.",
    10: "Sua mensalidade esta 10 dias em atraso.",
    30: "Sua mensalidade esta 30 dias em atraso e o acesso pode ser bloqueado.",
}


class ErroDeCobranca(Exception):
    """Falha esperada no fluxo de cobranca."""


# ------------------------------------------------------------------ autorizacoes
def autorizar_debito(
    *,
    aluno,
    modalidade: str = AutorizacaoDeDebito.Modalidade.PIX_AUTOMATICO,
    chave_pix: str = "",
    limite=Decimal("0"),
    criada_por=None,
) -> AutorizacaoDeDebito:
    if modalidade not in dict(AutorizacaoDeDebito.Modalidade.choices):
        raise ErroDeCobranca("Modalidade de debito desconhecida.")
    if (
        modalidade == AutorizacaoDeDebito.Modalidade.PIX_AUTOMATICO
        and not (chave_pix or "").strip()
    ):
        raise ErroDeCobranca("Informe a chave Pix de quem vai pagar.")
    autorizacao, criada = AutorizacaoDeDebito.objects.get_or_create(
        aluno=aluno,
        modalidade=modalidade,
        defaults={
            "rede": aluno.rede,
            "chave_pix": chave_pix.strip(),
            "limite_por_cobranca": limite,
            "criada_por": criada_por,
        },
    )
    if not criada:
        raise ErroDeCobranca("Este aluno ja tem autorizacao dessa modalidade.")
    return autorizacao


def ativar_autorizacao(autorizacao: AutorizacaoDeDebito, identificador_no_banco: str = ""):
    """Confirmacao do banco/PSP: aqui a autorizacao passa a valer."""
    if autorizacao.situacao == AutorizacaoDeDebito.Situacao.CANCELADA:
        raise ErroDeCobranca("Autorizacao cancelada nao pode ser reativada; crie outra.")
    autorizacao.situacao = AutorizacaoDeDebito.Situacao.ATIVA
    autorizacao.autorizada_em = timezone.now()
    if identificador_no_banco:
        autorizacao.identificador_no_banco = identificador_no_banco
    autorizacao.save(update_fields=["situacao", "autorizada_em", "identificador_no_banco"])
    return autorizacao


def cancelar_autorizacao(autorizacao: AutorizacaoDeDebito, motivo: str = ""):
    autorizacao.situacao = AutorizacaoDeDebito.Situacao.CANCELADA
    autorizacao.cancelada_em = timezone.now()
    autorizacao.save(update_fields=["situacao", "cancelada_em"])
    CobrancaRecorrente.objects.filter(
        autorizacao=autorizacao,
        situacao__in=[CobrancaRecorrente.Situacao.PREVISTA, CobrancaRecorrente.Situacao.ENVIADA],
    ).update(situacao=CobrancaRecorrente.Situacao.CANCELADA)
    return autorizacao


# ------------------------------------------------------------------ cobrancas do mes
def _valor_do_aluno(aluno) -> Decimal:
    from financeiro.models import Pagamento

    ultimo = (
        Pagamento.todos.filter(rede=aluno.rede, usuario=aluno.user)
        .order_by("-data_fim", "-id")
        .first()
    )
    if ultimo is not None and ultimo.valor_pago:
        return Decimal(ultimo.valor_pago)
    return Decimal("0.00")


def gerar_cobrancas_do_mes(
    rede, competencia: date, dia_do_vencimento: int = 10, dry_run: bool = False
) -> dict:
    """Cria a cobranca da competencia para quem tem autorizacao ativa (idempotente)."""
    from usuarios.models import Usuario

    competencia = competencia.replace(day=1)
    vencimento = competencia + timedelta(days=max(0, min(27, dia_do_vencimento - 1)))
    alunos = Usuario.todos.filter(rede=rede, status_user="Ativo").select_related("unidade")
    criadas, puladas, sem_autorizacao = [], [], []
    for aluno in alunos:
        autorizacao = AutorizacaoDeDebito.objects.filter(
            aluno=aluno, situacao=AutorizacaoDeDebito.Situacao.ATIVA
        ).first()
        if autorizacao is None:
            sem_autorizacao.append(aluno.nome)
            continue
        if CobrancaRecorrente.objects.filter(aluno=aluno, competencia=competencia).exists():
            puladas.append(aluno.nome)
            continue
        valor = _valor_do_aluno(aluno)
        criadas.append({"aluno": aluno.nome, "valor": valor})
        if dry_run:
            continue
        cobranca = CobrancaRecorrente.objects.create(
            rede=rede,
            unidade=aluno.unidade,
            aluno=aluno,
            autorizacao=autorizacao,
            competencia=competencia,
            valor=valor,
            vencimento=vencimento,
        )
        EventoDaCobranca.objects.create(
            cobranca=cobranca,
            tipo=EventoDaCobranca.Tipo.CRIADA,
            detalhe=f"Cobranca de {competencia:%m/%Y} criada.",
        )
    return {
        "competencia": competencia,
        "dry_run": dry_run,
        "criadas": criadas,
        "ja_existiam": puladas,
        "sem_autorizacao": sem_autorizacao,
        "total_de_alunos": alunos.count(),
    }


def enviar_cobranca(cobranca: CobrancaRecorrente, simulado: bool = True) -> CobrancaRecorrente:
    """Manda a cobranca para o banco. Sem PSP configurado, o envio e simulado e fica declarado."""
    if cobranca.situacao not in {
        CobrancaRecorrente.Situacao.PREVISTA,
        CobrancaRecorrente.Situacao.RECUSADA,
    }:
        raise ErroDeCobranca("Esta cobranca nao esta em estado de envio.")
    if cobranca.autorizacao is None or not cobranca.autorizacao.esta_ativa:
        raise ErroDeCobranca("Sem autorizacao ativa: envie para a regua de contato.")
    cobranca.situacao = CobrancaRecorrente.Situacao.ENVIADA
    cobranca.tentativas += 1
    cobranca.identificador_no_banco = f"SIM-{cobranca.pk:08d}"
    cobranca.save(update_fields=["situacao", "tentativas", "identificador_no_banco"])
    EventoDaCobranca.objects.create(
        cobranca=cobranca,
        tipo=EventoDaCobranca.Tipo.ENVIADA,
        detalhe="Envio simulado (sem PSP configurado)." if simulado else "Enviado ao banco.",
    )
    return cobranca


def registrar_lembrete(cobranca: CobrancaRecorrente, mensagem: str = "") -> EventoDaCobranca:
    texto = mensagem or ETAPAS_DA_REGUA.get(cobranca.dias_de_atraso, "Aviso de cobranca.")
    return EventoDaCobranca.objects.create(
        cobranca=cobranca, tipo=EventoDaCobranca.Tipo.LEMBRETE, detalhe=texto
    )


@transaction.atomic
def processar_retorno(
    cobranca: CobrancaRecorrente, tipo: str, dados: dict | None = None, motivo: str = ""
) -> dict:
    """Trata o retorno do banco: confirma pagamento (uma vez), recusa ou devolucao."""
    dados = dados or {}
    if tipo == "pago":
        if cobranca.situacao == CobrancaRecorrente.Situacao.PAGA:
            EventoDaCobranca.objects.create(
                cobranca=cobranca,
                tipo=EventoDaCobranca.Tipo.PAGA,
                detalhe="Retorno repetido: pagamento ja registrado, nada duplicado.",
                dados=dados,
            )
            return {
                "situacao": cobranca.situacao,
                "pagamento": cobranca.pagamento_id,
                "duplicado": True,
            }
        pagamento = _registrar_pagamento(cobranca)
        cobranca.situacao = CobrancaRecorrente.Situacao.PAGA
        cobranca.pago_em = timezone.now()
        cobranca.motivo_da_recusa = ""
        cobranca.pagamento = pagamento
        cobranca.save(update_fields=["situacao", "pago_em", "motivo_da_recusa", "pagamento"])
        EventoDaCobranca.objects.create(
            cobranca=cobranca,
            tipo=EventoDaCobranca.Tipo.PAGA,
            detalhe=f"Pagamento {pagamento.pk} registrado.",
            dados=dados,
        )
        return {"situacao": cobranca.situacao, "pagamento": pagamento.pk, "duplicado": False}

    if tipo in {"recusado", "devolvido"}:
        cobranca.situacao = CobrancaRecorrente.Situacao.RECUSADA
        cobranca.motivo_da_recusa = (
            motivo
            or dados.get("motivo")
            or ("devolvido pelo banco" if tipo == "devolvido" else "recusado pelo banco")
        )[:200]
        cobranca.save(update_fields=["situacao", "motivo_da_recusa"])
        EventoDaCobranca.objects.create(
            cobranca=cobranca,
            tipo=(
                EventoDaCobranca.Tipo.DEVOLVIDA
                if tipo == "devolvido"
                else EventoDaCobranca.Tipo.RECUSADA
            ),
            detalhe=cobranca.motivo_da_recusa,
            dados=dados,
        )
        return {"situacao": cobranca.situacao, "motivo": cobranca.motivo_da_recusa}

    raise ErroDeCobranca(f"Retorno desconhecido: {tipo}")


def _registrar_pagamento(cobranca: CobrancaRecorrente):
    """Cria a mensalidade paga a partir da cobranca confirmada."""
    from financeiro.models import Pagamento, Plano

    plano = (
        Plano.objects.filter(rede=cobranca.rede, unidade=cobranca.unidade).order_by("valor").last()
    )
    inicio = cobranca.vencimento
    return Pagamento.objects.create(
        rede=cobranca.rede,
        unidade=cobranca.unidade,
        usuario=cobranca.aluno.user,
        plano=plano,
        valor_pago=cobranca.valor,
        data_inicio=inicio,
        data_fim=inicio + timedelta(days=DIAS_DE_RECORRENCIA),
        status="pago",
        transaction_id=cobranca.identificador_no_banco or "",
    )


# ------------------------------------------------------------------ regua de cobranca
def fila_da_regua(rede, limite: int = 50) -> list[dict]:
    """Quem precisa de contato hoje, com a mensagem pronta da etapa."""
    hoje = timezone.localdate()
    cobrancas = (
        CobrancaRecorrente.objects.filter(
            rede=rede,
            situacao__in=[
                CobrancaRecorrente.Situacao.PREVISTA,
                CobrancaRecorrente.Situacao.ENVIADA,
                CobrancaRecorrente.Situacao.RECUSADA,
            ],
            vencimento__lte=hoje + timedelta(days=3),
        )
        .select_related("aluno", "unidade")
        .order_by("vencimento")[:limite]
    )
    fila = []
    for cobranca in cobrancas:
        etapa = cobranca.dias_de_atraso
        fila.append(
            {
                "cobranca": cobranca,
                "etapa": etapa,
                "mensagem": ETAPAS_DA_REGUA.get(etapa, "Cobranca em aberto."),
            }
        )
    return fila


def processar_retornos_em_lote(rede, conteudo_csv: str) -> dict:
    """Le o arquivo de retorno do banco (cobranca, situacao, motivo) e aplica cada linha."""
    leitor = csv.DictReader(io.StringIO((conteudo_csv or "").strip()))
    if not leitor.fieldnames:
        raise ErroDeCobranca("Arquivo de retorno vazio ou sem cabecalho.")
    colunas = {campo.strip().lower(): campo for campo in leitor.fieldnames}
    if "cobranca" not in colunas or "situacao" not in colunas:
        raise ErroDeCobranca("O retorno precisa das colunas cobranca e situacao.")
    aplicados, ignorados = 0, []
    for linha in leitor:
        try:
            identificador = int((linha.get(colunas["cobranca"]) or "0").strip())
        except ValueError:
            ignorados.append(linha)
            continue
        cobranca = CobrancaRecorrente.objects.filter(pk=identificador, rede=rede).first()
        if cobranca is None:
            ignorados.append(linha)
            continue
        situacao = (linha.get(colunas["situacao"]) or "").strip().lower()
        if situacao not in {"pago", "recusado", "devolvido"}:
            ignorados.append(linha)
            continue
        motivo = (
            (linha.get(colunas.get("motivo", ""), "") or "").strip() if "motivo" in colunas else ""
        )
        processar_retorno(cobranca, situacao, {"origem": "arquivo de retorno"}, motivo=motivo)
        aplicados += 1
    return {
        "aplicados": aplicados,
        "ignorados": len(ignorados),
        "ignorados_detalhe": ignorados[:20],
    }


def resumo_da_cobranca(rede, competencia: date | None = None) -> dict:
    competencia = (competencia or timezone.localdate()).replace(day=1)
    do_mes = CobrancaRecorrente.objects.filter(rede=rede, competencia=competencia)
    pagas = do_mes.filter(situacao=CobrancaRecorrente.Situacao.PAGA)
    recusadas = do_mes.filter(situacao=CobrancaRecorrente.Situacao.RECUSADA)
    previstas = do_mes.filter(
        situacao__in=[CobrancaRecorrente.Situacao.PREVISTA, CobrancaRecorrente.Situacao.ENVIADA]
    )
    total = do_mes.count()
    motivos: dict[str, int] = {}
    for cobranca in recusadas:
        chave = cobranca.motivo_da_recusa or "sem motivo informado"
        motivos[chave] = motivos.get(chave, 0) + 1
    return {
        "competencia": competencia,
        "total": total,
        "pagas": pagas.count(),
        "recusadas": recusadas.count(),
        "em_aberto": previstas.count(),
        "taxa_de_sucesso": round(pagas.count() * 100 / total, 1) if total else 0.0,
        "valor_recebido": sum((cobranca.valor for cobranca in pagas), Decimal("0")),
        "valor_em_aberto": sum((cobranca.valor for cobranca in previstas), Decimal("0")),
        "motivos_de_recusa": sorted(motivos.items(), key=lambda item: -item[1]),
        "autorizacoes_ativas": AutorizacaoDeDebito.objects.filter(
            rede=rede, situacao=AutorizacaoDeDebito.Situacao.ATIVA
        ).count(),
    }


# ------------------------------------------------------------------ inadimplencia
#: Faixas de atraso usadas na tela e na regua (mesmos cortes das etapas).
FAIXAS_DE_ATRASO = [
    ("1_a_5", "Ate 5 dias"),
    ("6_a_15", "6 a 15 dias"),
    ("16_a_30", "16 a 30 dias"),
    ("mais_de_30", "Mais de 30 dias"),
]


def faixa_do_atraso(dias: int) -> str:
    if dias <= 5:
        return "1_a_5"
    if dias <= 15:
        return "6_a_15"
    if dias <= 30:
        return "16_a_30"
    return "mais_de_30"


def lista_de_inadimplentes(rede, faixa: str = "", limite: int = 200) -> list[dict]:
    """Cobrancas vencidas com o que ja foi tentado, da mais antiga para a mais nova."""
    hoje = timezone.localdate()
    cobrancas = (
        CobrancaRecorrente.objects.filter(
            rede=rede,
            situacao__in=[
                CobrancaRecorrente.Situacao.PREVISTA,
                CobrancaRecorrente.Situacao.ENVIADA,
                CobrancaRecorrente.Situacao.RECUSADA,
            ],
            vencimento__lt=hoje,
        )
        .select_related("aluno", "unidade")
        .order_by("vencimento")[:limite]
    )
    linhas = []
    for cobranca in cobrancas:
        dias = cobranca.dias_de_atraso
        if faixa and faixa_do_atraso(dias) != faixa:
            continue
        ultimo_lembrete = (
            cobranca.eventos.filter(tipo=EventoDaCobranca.Tipo.LEMBRETE)
            .order_by("-criado_em")
            .first()
        )
        linhas.append(
            {
                "cobranca": cobranca,
                "dias": dias,
                "faixa": faixa_do_atraso(dias),
                "mensagem": ETAPAS_DA_REGUA.get(dias, "Cobranca em aberto."),
                "ultimo_lembrete_em": ultimo_lembrete.criado_em if ultimo_lembrete else None,
                "tentativas": cobranca.tentativas,
            }
        )
    return linhas


def resumo_da_inadimplencia(rede) -> dict:
    """Quanto esta vencido, por faixa — o numero que o dono da academia olha primeiro."""
    hoje = timezone.localdate()
    vencidas = CobrancaRecorrente.objects.filter(
        rede=rede,
        situacao__in=[
            CobrancaRecorrente.Situacao.PREVISTA,
            CobrancaRecorrente.Situacao.ENVIADA,
            CobrancaRecorrente.Situacao.RECUSADA,
        ],
        vencimento__lt=hoje,
    )
    por_faixa = {
        chave: {"quantidade": 0, "valor": Decimal("0")} for chave, _rotulo in FAIXAS_DE_ATRASO
    }
    total = Decimal("0")
    for cobranca in vencidas:
        chave = faixa_do_atraso(cobranca.dias_de_atraso)
        por_faixa[chave]["quantidade"] += 1
        por_faixa[chave]["valor"] += cobranca.valor or Decimal("0")
        total += cobranca.valor or Decimal("0")
    return {
        "quantidade_vencidas": vencidas.count(),
        "valor_vencido": total,
        "por_faixa": por_faixa,
        "mais_antiga": vencidas.order_by("vencimento").first(),
    }
