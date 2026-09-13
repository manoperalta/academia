#!/usr/bin/env python3
"""Acrescenta os modelos do portal na lista de excecao do teste de isolamento."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = ["portal_do_aluno.listadeespera", "portal_do_aluno.preferenciadenotificacao"]

alvo = None
for arquivo in (RAIZ / "tests").glob("*.py"):
    if "api.tarefaassincrona" in arquivo.read_text(encoding="utf-8"):
        alvo = arquivo
        break
if alvo is None:
    raise SystemExit("ERRO: nao achei a lista de excecao do isolamento")

texto = alvo.read_text(encoding="utf-8")
faltando = [modelo for modelo in MODELOS if f'"{modelo}"' not in texto]
if not faltando:
    print("isolamento: ja registrados")
else:
    linhas = texto.splitlines()
    inicio = next(i for i, linha in enumerate(linhas) if "api.tarefaassincrona" in linha)
    indentacao = re.match(r"\s*", linhas[inicio]).group(0)
    for posicao, modelo in enumerate(faltando):
        linhas.insert(inicio + 1 + posicao, f'{indentacao}"{modelo}",')
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"isolamento: {len(faltando)} modelo(s) acrescentados em {alvo.name}")

faltando_depois = [m for m in MODELOS if f'"{m}"' not in alvo.read_text(encoding="utf-8")]
if faltando_depois:
    raise SystemExit(f"ERRO: continuam faltando {faltando_depois}")
