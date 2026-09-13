"""Servicos do portal do aluno: agenda, pagamentos, ficha de saude e preferencias."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from agendamento.models import Agendamento
from financeiro.models import Pagamento
from painel.models import Painel
from portal_do_aluno.models import ListaDeEspera, PreferenciaDeNotificacao
from usuarios.models import FichaSaude


class ErroDoPortal(Exception):
    """Falha esperada no portal do aluno (mensagem pronta para a tela)."""


# ------------------------------------------------------------------ agenda
def turmas_disponiveis(aluno, dias: int = 14) -> list[dict]:
    """Turmas da rede do aluno no periodo, com vagas e o que ele ja agendou."""
    hoje = timezone.localdate()
    fim = hoje + timedelta(days=dias)
    turmas = (
        Painel.todos.filter(
            rede=aluno.rede, data__gte=hoje, data__lte=fim, arquivado_em__isnull=True
        )
        .select_related("unidade", "responsavel")
        .order_by("data", "hora_inicio")
    )
    meus = set(
        Agendamento.todos.filter(aluno=aluno.user, arquivado_em__isnull=True)
        .exclude(status="Cancelado")
        .values_list("painel_id", flat=True)
    )
    linhas = []
    for turma in turmas:
        ocupados = (
            Agendamento.todos.filter(painel=turma, arquivado_em__isnull=True)
            .exclude(status="Cancelado")
            .count()
        )
        linhas.append(
            {
                "turma": turma,
                "ocupados": ocupados,
                "vagas": max(0, turma.numero_de_user - ocupados),
                "cheia": ocupados >= turma.numero_de_user,
                "ja_agendei": turma.pk in meus,
                "na_espera": ListaDeEspera.objects.filter(turma=turma, aluno=aluno).exists(),
            }
        )
    return linhas


@transaction.atomic
def agendar(*, aluno, turma: Painel) -> Agendamento:
    """Agenda o aluno na turma, respeitando capacidade e evitando duplicidade."""
    if turma.rede_id != aluno.rede_id:
        raise ErroDoPortal("Esta turma e de outra academia.")
    if turma.arquivado_em is not None:
        raise ErroDoPortal("Esta turma nao esta mais disponivel.")
    if turma.data < timezone.localdate():
        raise ErroDoPortal("Esta turma ja aconteceu.")
    existente = (
        Agendamento.todos.filter(aluno=aluno.user, painel=turma, arquivado_em__isnull=True)
        .exclude(status="Cancelado")
        .first()
    )
    if existente is not None:
        raise ErroDoPortal("Voce ja esta nesta turma.")
    ocupados = (
        Agendamento.objects.filter(painel=turma, arquivado_em__isnull=True)
        .exclude(status="Cancelado")
        .count()
    )
    if ocupados >= turma.numero_de_user:
        raise ErroDoPortal("Turma cheia: entre na lista de espera que avisamos quando abrir vaga.")
    from django.conf import settings

    momento = timezone.datetime.combine(turma.data, turma.hora_inicio)
    if settings.USE_TZ:
        momento = timezone.make_aware(momento)
    return Agendamento.todos.create(
        rede=aluno.rede,
        unidade=turma.unidade,
        painel=turma,
        aluno=aluno.user,
        data_agendamento=momento,
        status="pendente",
    )


@transaction.atomic
def entrar_na_lista_de_espera(*, aluno, turma: Painel) -> ListaDeEspera:
    if turma.rede_id != aluno.rede_id:
        raise ErroDoPortal("Esta turma e de outra academia.")
    entrada, criada = ListaDeEspera.objects.get_or_create(turma=turma, aluno=aluno)
    if not criada:
        raise ErroDoPortal("Voce ja esta na lista de espera desta turma.")
    return entrada


@transaction.atomic
def cancelar_agendamento(*, aluno, agendamento: Agendamento) -> dict:
    """Cancela o proprio agendamento e chama o proximo da fila de espera."""
    if agendamento.aluno_id != aluno.user_id:
        raise ErroDoPortal("Este agendamento nao e seu.")
    if agendamento.status == "Cancelado":
        raise ErroDoPortal("Este agendamento ja foi cancelado.")
    agendamento.status = "Cancelado"
    agendamento.save(update_fields=["status"])
    proximo = (
        ListaDeEspera.objects.filter(turma=agendamento.painel, avisado=False)
        .order_by("criado_em")
        .first()
    )
    if proximo is not None:
        proximo.avisado = True
        proximo.save(update_fields=["avisado"])
    return {"agendamento": agendamento, "avisado": proximo.aluno.nome if proximo else ""}


def meus_agendamentos(aluno, limite: int = 30):
    return (
        Agendamento.todos.filter(aluno=aluno.user, arquivado_em__isnull=True)
        .select_related("painel", "painel__unidade")
        .order_by("-painel__data")[:limite]
    )


# ------------------------------------------------------------------ pagamentos
def minhas_faturas(aluno, limite: int = 24) -> dict:
    """Faturas do aluno com o que esta em aberto e o Pix pronto para pagar."""
    faturas = (
        Pagamento.todos.filter(rede=aluno.rede, usuario=aluno.user)
        .select_related("plano")
        .order_by("-data_inicio")[:limite]
    )
    hoje = timezone.localdate()
    em_aberto = [
        fatura
        for fatura in faturas
        if fatura.status != "pago" or (fatura.data_fim and fatura.data_fim < hoje)
    ]
    valor_aberto = sum((fatura.valor_pago or Decimal("0") for fatura in em_aberto), Decimal("0"))
    return {
        "faturas": list(faturas),
        "em_aberto": em_aberto,
        "valor_em_aberto": valor_aberto,
        "proxima": next(
            (
                fatura
                for fatura in faturas
                if fatura.status == "pago" and fatura.data_fim and fatura.data_fim >= hoje
            ),
            None,
        ),
    }


# ------------------------------------------------------------------ ficha de saude e preferencias
def salvar_ficha(
    *,
    aluno,
    altura=0,
    peso=0,
    restricoes: str = "",
    prescricoes: str = "",
    usa_medicamento: bool = False,
    qual_medicamento: str = "",
    observacoes: str = "",
) -> FichaSaude:
    """O aluno preenche/atualiza a propria ficha — dado sensivel, com registro de quem mexeu."""
    ficha, _criada = FichaSaude.todos.get_or_create(
        rede=aluno.rede, usuario=aluno, defaults={"unidade": aluno.unidade}
    )
    ficha.altura = altura or ficha.altura
    ficha.peso = peso or ficha.peso
    ficha.restricoes = restricoes
    ficha.prescricoes = prescricoes
    ficha.usa_medicamento = usa_medicamento
    ficha.qual_medicamento = qual_medicamento
    ficha.obs = observacoes
    ficha.save()
    return ficha


def preferencias_do_aluno(aluno) -> PreferenciaDeNotificacao:
    preferencias, _criada = PreferenciaDeNotificacao.objects.get_or_create(aluno=aluno)
    return preferencias


def salvar_preferencias(
    *,
    aluno,
    canal: str,
    avisar_vencimento: bool = True,
    avisar_aula: bool = True,
    avisar_aniversario: bool = False,
    receber_novidades: bool = False,
) -> PreferenciaDeNotificacao:
    if canal not in dict(PreferenciaDeNotificacao.Canal.choices):
        raise ErroDoPortal("Canal de aviso desconhecido.")
    preferencias = preferencias_do_aluno(aluno)
    preferencias.canal = canal
    preferencias.avisar_vencimento = avisar_vencimento
    preferencias.avisar_aula = avisar_aula
    preferencias.avisar_aniversario = avisar_aniversario
    preferencias.receber_novidades = receber_novidades
    preferencias.save()
    return preferencias


def meus_dados(aluno) -> dict:
    """Direito de acesso (LGPD): tudo o que a academia guarda sobre o aluno, em um arquivo."""
    from area_do_aluno.models import CheckinDoAluno
    from treinos.models import AvaliacaoFisica, Treino

    ficha = FichaSaude.todos.filter(usuario=aluno).first()
    return {
        "gerado_em": timezone.now().isoformat(),
        "titular": {
            "nome": aluno.nome,
            "login": aluno.user.username,
            "email": aluno.email_user,
            "telefone": aluno.telefone_user,
            "situacao": aluno.status_user,
            "cpf": aluno.cpf_cnpj_user,
        },
        "ficha_de_saude": {
            "altura": str(ficha.altura) if ficha else "",
            "peso": str(ficha.peso) if ficha else "",
            "restricoes": ficha.restricoes if ficha else "",
            "prescricoes": ficha.prescricoes if ficha else "",
        },
        "treinos": [
            {
                "nome": treino.nome,
                "objetivo": treino.objetivo,
                "exercicios": [
                    {
                        "nome": exercicio.nome,
                        "series": exercicio.series,
                        "repeticoes": exercicio.repeticoes,
                    }
                    for exercicio in treino.exercicios.all()
                ],
            }
            for treino in Treino.objects.filter(aluno=aluno)
        ],
        "avaliacoes": [
            {
                "data": avaliacao.data.isoformat(),
                "peso": str(avaliacao.peso),
                "percentual_de_gordura": str(avaliacao.percentual_de_gordura),
                "medidas": avaliacao.medidas,
            }
            for avaliacao in AvaliacaoFisica.objects.filter(aluno=aluno)
        ],
        "pagamentos": [
            {
                "inicio": fatura.data_inicio.isoformat() if fatura.data_inicio else "",
                "valor": str(fatura.valor_pago),
                "situacao": fatura.status,
            }
            for fatura in Pagamento.todos.filter(rede=aluno.rede, usuario=aluno.user)
        ],
        "checkins": [
            {"em": checkin.criado_em.isoformat(), "unidade": checkin.unidade.nome}
            for checkin in CheckinDoAluno.objects.filter(aluno=aluno).select_related("unidade")[
                :200
            ]
        ],
    }


def meus_dados_em_json(aluno) -> bytes:
    return json.dumps(meus_dados(aluno), ensure_ascii=False, indent=2).encode("utf-8")
