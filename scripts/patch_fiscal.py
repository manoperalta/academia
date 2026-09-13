#!/usr/bin/env python3
"""Fase 8 (fiscal): modulo FISCAL no enum, na matriz do gestor e no menu."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ANCORA_ENUM = '    COBRANCA = "cobranca", "Cobranca recorrente"'
MEMBROS = ['    FISCAL = "fiscal", "Fiscal (NFS-e)"']
ANCORA_MATRIZ = '        Modulo.COBRANCA: "editar",'
MATRIZ = ['        Modulo.FISCAL: "editar",']
ANCORA_MENU = '    Modulo.COBRANCA: "cobranca:painel",'
ROTAS = ['    Modulo.FISCAL: "fiscal:painel",']


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
    _inserir(permissoes, ANCORA_ENUM, MEMBROS, 'FISCAL = "fiscal"', "enum de modulos")
    _inserir(permissoes, ANCORA_MATRIZ, MATRIZ, 'Modulo.FISCAL: "editar"', "matriz do gestor")
    _inserir(RAIZ / "gestao" / "menu.py", ANCORA_MENU, ROTAS, "fiscal:painel", "rotas do menu")
