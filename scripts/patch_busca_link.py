#!/usr/bin/env python3
"""Fase 8 (busca): caixa de busca no cabecalho do painel."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RELATIVO = "gestao/templates/gestao/base.html"
ANCORA = '<form method="post" action="{% url \'gestao:selecionar_unidade\' %}"'

BLOCO = (
    '<form method="get" action="{% url \'busca:resultados\' %}" class="hidden items-center gap-2 '
    'sm:flex">\n'
    '        <input name="q" value="{{ request.GET.q|default:\'\' }}" placeholder="Buscar no painel" '
    'aria-label="Buscar no painel"\n'
    '               class="w-56 rounded-lg border border-slate-300 px-3 py-1.5 text-sm">\n'
    '        <button class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Buscar</button>\n'
    "      </form>\n      "
)


def aplicar() -> None:
    caminho = RAIZ / RELATIVO
    texto = caminho.read_text(encoding="utf-8")
    if "busca:resultados" in texto:
        print("base.html: caixa de busca ja presente")
        return
    if texto.count(ANCORA) != 1:
        raise SystemExit(f"ERRO: ancora nao unica em {RELATIVO} ({texto.count(ANCORA)})")
    texto = texto.replace(ANCORA, BLOCO + ANCORA, 1)
    caminho.write_text(texto, encoding="utf-8")
    if "busca:resultados" not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: caixa de busca nao entrou")
    print("base.html: caixa de busca no cabecalho")


if __name__ == "__main__":
    aplicar()
