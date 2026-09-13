#!/usr/bin/env python3
"""Acrescenta modelos na lista de excecao do teste de isolamento (busca pelo conteudo, sem ancora fragil)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = sys.argv[1:] or ["conta.chamadodesuporte", "conta.mensagemdochamado"]

alvo = None
for arquivo in (RAIZ / "tests").glob("*.py"):
    if "api.tarefaassincrona" in arquivo.read_text(encoding="utf-8"):
        alvo = arquivo
        break
if alvo is None:
    raise SystemExit("ERRO: nao achei a lista de excecao do isolamento")

for modelo in MODELOS:
    texto = alvo.read_text(encoding="utf-8")
    if f'"{modelo}"' in texto:
        print(f"{modelo}: ja registrado")
        continue
    linhas = texto.splitlines()
    inicio = next(i for i, linha in enumerate(linhas) if "api.tarefaassincrona" in linha)
    indentacao = re.match(r"\s*", linhas[inicio]).group(0)
    linhas.insert(inicio + 1, f'{indentacao}"{modelo}",')
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    if f'"{modelo}"' not in alvo.read_text(encoding="utf-8"):
        raise SystemExit(f"ERRO: {modelo} nao entrou")
    print(f"{modelo}: registrado em {alvo.name}")
