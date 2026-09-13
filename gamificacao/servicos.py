"""Pontuacao, nivel, conquistas e ranking (gamificacao da fase 8)."""

from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone

from gamificacao.models import (
    Conquista,
    ConquistaDoAluno,
    EventoDePontos,
    LancamentoDePontos,
    RegraDePontos,
    SaldoDePontos,
)

PONTOS_POR_NIVEL = 500


class ErroDeGamificacao(Exception):
    """Operacao recusada."""


def regra_do_evento(rede, evento: str) -> RegraDePontos | None:
    return RegraDePontos.objects.filter(rede=rede, evento=evento, ativo=True).first()


def nivel_de(pontos: int) -> int:
    return 1 + int(pontos // PONTOS_POR_NIVEL)


def pontuar(aluno, evento: str, referencia: str = "", quantidade: int = 1) -> dict:
    """Lanca pontos do evento, respeitando o limite diario; devolve conquistas novas."""
    if evento not in EventoDePontos.values:
        raise ErroDeGamificacao(f"evento desconhecido: {evento}")
    regra = regra_do_evento(aluno.rede, evento)
    if regra is None:
        return {"pontuou": False, "motivo": "sem regra de pontos para o evento", "conquistas": []}

    saldo, _criado = SaldoDePontos.objects.get_or_create(rede=aluno.rede, aluno=aluno)
    if regra.limite_diario:
        hoje = timezone.localdate()
        registrados = LancamentoDePontos.objects.filter(
            saldo=saldo, evento=evento, pontos__gt=0, criado_em__date=hoje
        ).count()
        if registrados >= regra.limite_diario:
            return {"pontuou": False, "motivo": "limite diario atingido", "conquistas": []}

    ganho = regra.pontos * max(1, quantidade)
    _lancamento, criado = LancamentoDePontos.objects.get_or_create(
        saldo=saldo,
        evento=evento,
        referencia=referencia or timezone.now().strftime("%Y%m%d%H%M%S"),
        defaults={"pontos": ganho},
    )
    if not criado:
        return {"pontuou": False, "motivo": "ja lancado", "conquistas": []}

    novas = _conferir_conquistas(saldo, evento)
    saldo.pontos = (saldo.pontos or 0) + ganho + sum(item["bonus"] for item in novas)
    saldo.nivel = nivel_de(saldo.pontos)
    saldo.save(update_fields=["pontos", "nivel", "atualizado_em"])
    return {
        "pontuou": True,
        "pontos": ganho,
        "total": saldo.pontos,
        "nivel": saldo.nivel,
        "conquistas": novas,
    }


def _conferir_conquistas(saldo: SaldoDePontos, evento: str) -> list[dict]:
    quantidade = LancamentoDePontos.objects.filter(saldo=saldo, evento=evento, pontos__gt=0).count()
    novas = []
    for conquista in Conquista.objects.filter(
        rede=saldo.rede, evento=evento, ativa=True, quantidade__lte=quantidade
    ):
        _registro, criado = ConquistaDoAluno.objects.get_or_create(
            aluno=saldo.aluno, conquista=conquista
        )
        if criado:
            novas.append(
                {
                    "nome": conquista.nome,
                    "icone": conquista.icone or "🏅",
                    "bonus": conquista.pontos_bonus,
                }
            )
    return novas


def saldo_do_aluno(aluno) -> dict:
    """Saldo do aluno; funciona mesmo antes do primeiro ponto (saldo ainda nao criado)."""
    saldo = SaldoDePontos.objects.filter(aluno=aluno).first()
    pontos = saldo.pontos if saldo else 0
    nivel = saldo.nivel if saldo else nivel_de(pontos)
    lancamentos = list(saldo.lancamentos.all()[:20]) if saldo else []
    conquistas = list(ConquistaDoAluno.objects.filter(aluno=aluno).select_related("conquista"))
    return {
        "pontos": pontos,
        "nivel": nivel,
        "para_o_proximo_nivel": max(0, nivel * PONTOS_POR_NIVEL - pontos),
        "lancamentos": lancamentos,
        "conquistas": conquistas,
    }


def ranking(rede=None, unidade=None, limite: int = 10, desde=None) -> list[dict]:
    """Ranking por periodo (padrao: mes corrente) — opcionalmente por unidade."""
    desde = desde or timezone.localdate().replace(day=1)
    consulta = LancamentoDePontos.objects.filter(pontos__gt=0, criado_em__date__gte=desde)
    if unidade is not None:
        consulta = consulta.filter(saldo__aluno__unidade=unidade)
    elif rede is not None:
        consulta = consulta.filter(saldo__rede=rede)
    agrupado = (
        consulta.values("saldo__aluno__nome", "saldo__aluno_id")
        .annotate(pontos=Sum("pontos"))
        .order_by("-pontos")[:limite]
    )
    return [
        {
            "posicao": posicao,
            "aluno": linha["saldo__aluno_id"],
            "nome": linha["saldo__aluno__nome"],
            "pontos": linha["pontos"],
        }
        for posicao, linha in enumerate(agrupado, start=1)
    ]


def engajamento_do_mes(rede) -> dict:
    """Quantos alunos pontuaram no mes (indicador de engajamento para o painel)."""
    desde = timezone.localdate().replace(day=1)
    ativos = (
        LancamentoDePontos.objects.filter(
            saldo__rede=rede, pontos__gt=0, criado_em__date__gte=desde
        )
        .values("saldo__aluno")
        .distinct()
        .count()
    )
    total = (
        LancamentoDePontos.objects.filter(
            saldo__rede=rede, pontos__gt=0, criado_em__date__gte=desde
        ).aggregate(total=Sum("pontos"))["total"]
        or 0
    )
    return {
        "alunos_pontuando": ativos,
        "pontos_distribuidos": total,
        "media_por_aluno": round(total / ativos, 1) if ativos else 0,
    }
