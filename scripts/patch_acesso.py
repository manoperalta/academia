#!/usr/bin/env python3
"""Fase 8 (acesso): modulos ACESSO e PARCEIROS no enum, na matriz do gestor e no menu."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MEMBROS = [
    '    ACESSO = "acesso", "Controle de acesso"',
    '    PARCEIROS = "parceiros", "Parceiros e conciliacao"',
]
MATRIZ_GESTOR = [
    '        Modulo.ACESSO: "editar",',
    '        Modulo.PARCEIROS: "editar",',
]
ROTAS = [
    '    Modulo.ACESSO: "acesso:painel",',
    '    Modulo.PARCEIROS: "acesso:parceiros",',
]

ANCORAS = {
    "enum": ('    RETENCAO = "retencao", "Retencao de alunos"', MEMBROS, 'ACESSO = "acesso"'),
    "matriz": ('        Modulo.CRM: "editar",', MATRIZ_GESTOR, 'Modulo.ACESSO: "editar"'),
    "menu": ('    Modulo.RETENCAO: "relacionamento:retencao",', ROTAS, "acesso:painel", "gestao/menu.py"),
}


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
    _inserir(permissoes, ANCORAS["enum"][0], ANCORAS["enum"][1], ANCORAS["enum"][2],
             "enum de modulos")
    _inserir(permissoes, ANCORAS["matriz"][0], ANCORAS["matriz"][1], ANCORAS["matriz"][2],
             "matriz do gestor")
    _inserir(RAIZ / "gestao" / "menu.py", ANCORAS["menu"][0], ANCORAS["menu"][1],
             ANCORAS["menu"][2], "rotas do menu")
