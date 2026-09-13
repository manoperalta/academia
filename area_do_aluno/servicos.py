"""Check-in e resumo do aluno no PWA."""

from __future__ import annotations

from django.utils import timezone

from area_do_aluno.models import CheckinDoAluno, OrigemDoCheckin


class ErroDeCheckin(Exception):
    """Check-in recusado."""


def registrar_checkin(aluno, unidade=None, origem: str = OrigemDoCheckin.PWA) -> CheckinDoAluno:
    """Registra a entrada (o aluno pode treinar em qualquer unidade da rede — RF-RED-003)."""
    unidade = unidade or aluno.unidade
    if unidade is None:
        raise ErroDeCheckin("aluno sem unidade vinculada")
    if unidade.rede_id != aluno.rede_id:
        raise ErroDeCheckin("unidade de outra rede")
    if getattr(aluno, "status_user", "") != "Ativo":
        raise ErroDeCheckin("matricula inativa: procure a recepcao")
    checkin = CheckinDoAluno.objects.create(
        rede=aluno.rede, aluno=aluno, unidade=unidade, origem=origem
    )
    from gamificacao.servicos import pontuar

    resultado = pontuar(aluno, "checkin", referencia=f"checkin-{checkin.pk}")
    return checkin, resultado


def resumo_do_aluno(aluno, unidade=None) -> dict:
    """Tudo que a tela inicial do aluno precisa, em uma consulta."""

    from gamificacao.servicos import saldo_do_aluno
    from nps.models import Pesquisa

    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    checkins = CheckinDoAluno.objects.filter(aluno=aluno)
    respondidas = set(
        __import__("nps.models", fromlist=["Resposta"])
        .Resposta.objects.filter(aluno=aluno)
        .values_list("pesquisa_id", flat=True)
    )
    pesquisas = [
        item
        for item in Pesquisa.objects.filter(rede=aluno.rede, ativa=True)
        if item.pk not in respondidas and item.aceita_resposta()
    ]
    comunicados = (
        __import__("rede.models", fromlist=["Comunicado"])
        .Comunicado.objects.filter(rede=aluno.rede, ativo=True)
        .order_by("-criado_em")[:5]
    )
    return {
        "aluno": aluno,
        "checkins_no_mes": checkins.filter(criado_em__date__gte=inicio_mes).count(),
        "checkins_recentes": checkins.select_related("unidade")[:5],
        "unidade_de_origem": unidade or aluno.unidade,
        "gamificacao": saldo_do_aluno(aluno),
        "pesquisas_abertas": pesquisas,
        "comunicados": comunicados,
    }
