#!/usr/bin/env python3
"""Fase 8 (midia): atalho para a midia da rede na tela de aulas."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RELATIVO = "aulas/templates/aulas/aulas_list.html"
ANCORA = "{% for aula in aulas %}"
BLOCO = (
    '<div class="mb-4 flex flex-wrap items-center gap-3">\n'
    '  <div class="mr-auto">\n'
    '    <h2 class="text-sm font-semibold text-slate-900">Vídeos e materiais</h2>\n'
    '    <p class="text-xs text-slate-500">Envie o vídeo da aula em partes, com conferência de '
    "integridade.</p>\n"
    "  </div>\n"
    '  <a href="{% url \'midia:lista\' %}" class="rounded-lg border border-slate-300 px-4 py-2 '
    'text-sm">Mídia da rede</a>\n'
    '  <a href="{% url \'midia:enviar\' %}" class="rounded-lg bg-slate-900 px-4 py-2 text-sm '
    'text-white">Enviar arquivo</a>\n'
    "</div>\n\n"
)


def aplicar() -> None:
    caminho = RAIZ / RELATIVO
    if not caminho.exists():
        raise SystemExit(f"ERRO: {RELATIVO} nao existe")
    texto = caminho.read_text(encoding="utf-8")
    if "midia:lista" in texto:
        print("aulas_list: atalho da midia ja presente")
        return
    if texto.count(ANCORA) != 1:
        raise SystemExit(f"ERRO: ancora nao unica em {RELATIVO}")
    texto = texto.replace(ANCORA, BLOCO + ANCORA, 1)
    caminho.write_text(texto, encoding="utf-8")
    if "midia:lista" not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: atalho nao entrou")
    print("aulas_list: atalho da midia adicionado")


if __name__ == "__main__":
    aplicar()
