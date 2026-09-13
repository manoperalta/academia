"""Contexto de template: rede e unidade atuais."""

from __future__ import annotations

from core.context import rede_atual, unidade_atual


def contexto_rede(request):
    """Disponibiliza ``rede``/``unidade`` (e apelidos em pt) para os templates."""
    rede = getattr(request, "rede", None) or rede_atual()
    unidade = getattr(request, "unidade", None) or unidade_atual()
    return {
        "rede": rede,
        "unidade": unidade,
        "rede_nome": rede.nome if rede else "",
        "unidade_nome": unidade.nome if unidade else "",
    }
