#!/usr/bin/env python3
"""Fase 8 (relacionamento): modulos CRM e RETENCAO no enum, na matriz, no menu e na suite."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MEMBROS = [
    '    CRM = "crm", "CRM e captacao"',
    '    RETENCAO = "retencao", "Retencao de alunos"',
]
MATRIZ_GESTOR = [
    '        Modulo.CRM: "editar",',
    '        Modulo.RETENCAO: "editar",',
]
ROTAS = [
    '    Modulo.CRM: "relacionamento:funil",',
    '    Modulo.RETENCAO: "relacionamento:retencao",',
]


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


def aplicar() -> None:
    permissoes = RAIZ / "gestao" / "permissoes.py"
    _inserir(
        permissoes,
        next(
            linha
            for linha in permissoes.read_text(encoding="utf-8").splitlines()
            if linha.startswith("    CATALOGO = ")
        ),
        MEMBROS,
        'CRM = "crm"',
        "enum de modulos",
    )
    _inserir(
        permissoes,
        '        Modulo.PRIVACIDADE: "ver",',
        MATRIZ_GESTOR,
        'Modulo.CRM: "editar"',
        "matriz do gestor de unidade",
    )
    _inserir(
        RAIZ / "gestao" / "menu.py",
        '    Modulo.AUDITORIA: "gestao:auditoria",',
        ROTAS,
        "relacionamento:funil",
        "rotas do menu",
    )


def incluir_testes() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"relacionamento"' in texto:
        print("pyproject: relacionamento ja na suite")
        return
    ancora = ', "midia"]'
    if ancora not in texto:
        raise SystemExit("ERRO: nao achei o testpaths")
    texto = texto.replace(ancora, ', "midia", "relacionamento"]', 1)
    caminho.write_text(texto, encoding="utf-8")
    print("pyproject: relacionamento na suite padrao")


if __name__ == "__main__":
    aplicar()
    incluir_testes()
    print("patch relacionamento concluido")
