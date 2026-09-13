#!/usr/bin/env python3
"""Corrige o nome do modelo na lista de excecao do teste de isolamento."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ERRADO = "painel_do_professor.substituicaodeturna"
CERTO = "painel_do_professor.substituicaodeturna".replace("deturna", "deturma")

for arquivo in (RAIZ / "tests").glob("*.py"):
    texto = arquivo.read_text(encoding="utf-8")
    if ERRADO not in texto:
        continue
    texto = texto.replace(ERRADO, CERTO)
    arquivo.write_text(texto, encoding="utf-8")
    if CERTO not in arquivo.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: correcao nao entrou")
    print(f"{arquivo.name}: {ERRADO} -> {CERTO}")
    break
else:
    raise SystemExit("ERRO: nao encontrei o nome errado")
