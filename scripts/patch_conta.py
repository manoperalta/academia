#!/usr/bin/env python3
"""Fase 8 (conta): modulo SUPORTE no enum, na matriz do gestor e no menu."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ANCORA_ENUM = '    PDV = "pdv", "PDV e estoque"'
MEMBROS = ['    SUPORTE = "suporte", "Suporte ao cliente"']
ANCORA_MATRIZ = '        Modulo.PDV: "editar",'
MATRIZ = ['        Modulo.SUPORTE: "editar",']
ANCORA_MENU = '    Modulo.PDV: "pdv:painel",'
ROTAS = ['    Modulo.SUPORTE: "conta:fila_suporte",']


def _inserir(caminho: Path, ancora: str, linhas: list[str], marcador: str, rotulo: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marcador in texto:
        print(f"{rotulo}: ja aplicado")
        return
    if texto.count(ancora) != 1:
        raise SystemExit(f"ERRO: ancora de {rotulo} nao e unica ({texto.count(ancora)})")
    texto = texto.replace(ancora, ancora + "\n" + "\n".join(linhas), 1)
    caminho.write_text(texto, encoding="utf-8")
    if marcador not in caminho.read_text(encoding="utf-8"):
        raise SystemExit(f"ERRO: {rotulo} nao entrou")
    print(f"{rotulo}: aplicado")


if __name__ == "__main__":
    permissoes = RAIZ / "gestao" / "permissoes.py"
    _inserir(permissoes, ANCORA_ENUM, MEMBROS, 'SUPORTE = "suporte"', "enum de modulos")
    _inserir(permissoes, ANCORA_MATRIZ, MATRIZ, 'Modulo.SUPORTE: "editar"', "matriz do gestor")
    _inserir(RAIZ / "gestao" / "menu.py", ANCORA_MENU, ROTAS, "conta:fila_suporte", "rotas do menu")
