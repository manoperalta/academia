#!/usr/bin/env python3
"""Aplica uma lista de ajustes (arquivo, trecho antigo, trecho novo) vinda de um JSON.

Falha alto se o trecho antigo nao existir; considera sucesso se o novo ja estiver no lugar.
Roda DENTRO do container, onde o repositorio esta em /app.

Uso: python scripts/aplica_ajustes.py scripts/ajustes_status.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/app")


def main() -> int:
    dados = json.loads((RAIZ / sys.argv[1]).read_text(encoding="utf-8"))
    todos = bool(dados.get("todos"))
    falhas = []
    for arquivo, antigo, novo in dados["ajustes"]:
        caminho = RAIZ / arquivo
        texto = caminho.read_text(encoding="utf-8")
        if antigo not in texto:
            estado = "ja aplicado" if novo in texto else "NAO ENCONTRADO"
            print(f"{arquivo}: {estado}")
            if estado == "NAO ENCONTRADO":
                falhas.append(arquivo)
            continue
        quantas = texto.count(antigo)
        caminho.write_text(texto.replace(antigo, novo, -1 if todos else 1), encoding="utf-8")
        print(f"{arquivo}: aplicado ({quantas}x)")
    if falhas:
        raise SystemExit("ERRO: ajuste nao aplicado em " + ", ".join(sorted(set(falhas))))
    print("ajustes aplicados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
