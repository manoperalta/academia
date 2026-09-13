"""Filtros usados pelos templates genericos do painel."""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def valor(objeto, campo: str):
    """Le um atributo (ou chama um metodo sem argumentos) pelo nome, com seguranca."""
    if objeto is None or not campo:
        return ""
    if hasattr(objeto, "get_" + campo + "_display"):
        return getattr(objeto, "get_" + campo + "_display")()
    atual = objeto
    for parte in str(campo).split("."):
        atual = getattr(atual, parte, None)
        if atual is None:
            return ""
    if callable(atual):
        try:
            return atual()
        except TypeError:
            return ""
    return atual


@register.filter
def moeda(valor_bruto) -> str:
    """Formata em Real (R$ 1.234,56)."""
    try:
        numero = float(valor_bruto)
    except (TypeError, ValueError):
        return "—"
    inteiro = f"{numero:,.2f}"
    return "R$ " + inteiro.replace(",", "#").replace(".", ",").replace("#", ".")
