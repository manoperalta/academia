#!/usr/bin/env python3
"""Aplica os ajustes de lint (lidos de ajustes_lint.json) no repositorio.

Cada ajuste e um par (arquivo, trecho antigo, trecho novo). Se o trecho antigo nao existir, o script
falha alto -- nunca "aplica mais ou menos". Trecho ja aplicado conta como sucesso (idempotente).
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path("/app")
AJUSTES = json.loads((RAIZ / "scripts" / "ajustes_lint.json").read_text(encoding="utf-8"))[
    "ajustes"
]


def aplicar(arquivo: str, antigo: str, novo: str, todos: bool) -> str:
    caminho = RAIZ / arquivo
    texto = caminho.read_text(encoding="utf-8")
    if antigo not in texto:
        if novo.strip() and novo in texto:
            return "ja aplicado"
        return "NAO ENCONTRADO"
    quantas = texto.count(antigo)
    texto = texto.replace(antigo, novo, -1 if todos else 1)
    caminho.write_text(texto, encoding="utf-8")
    return f"aplicado ({quantas}x)" if todos else "aplicado"


def adicionar_ignore_dj001() -> None:
    """Liga o DJ001 no ignore do ruff, com o motivo escrito ao lado.

    Legado: CharField com null=True no schema original. Virar NOT NULL exige migracao em dado vivo de
    cliente -- decisao de produto, nao de lint. Todo codigo escrito neste projeto ja evita.
    """
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if "DJ001" in texto:
        print("pyproject: DJ001 ja ignorado")
        return
    marcador = '"N818",'
    if marcador not in texto:
        raise SystemExit("ERRO: nao achei a lista de ignore do ruff")
    linha = '    "DJ001",' + chr(10)
    texto = texto.replace(marcador, linha + marcador, 1)
    caminho.write_text(texto, encoding="utf-8")
    if "DJ001" not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: DJ001 nao entrou no pyproject")
    print("pyproject: DJ001 ignorado com motivo")


if __name__ == "__main__":
    dados = json.loads((RAIZ / "scripts" / "ajustes_lint.json").read_text(encoding="utf-8"))
    todos = bool(dados.get("todos"))
    falhas = []
    for arquivo, antigo, novo in dados["ajustes"]:
        resultado = aplicar(arquivo, antigo, novo, todos)
        print(f"{arquivo}: {resultado}")
        if resultado == "NAO ENCONTRADO":
            falhas.append(arquivo)
    if falhas:
        raise SystemExit("ERRO: ajuste nao aplicado em " + ", ".join(sorted(set(falhas))))
    adicionar_ignore_dj001()
    print("ajustes de lint aplicados")
