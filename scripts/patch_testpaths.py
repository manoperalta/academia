#!/usr/bin/env python3
"""Garante que as pastas de teste estejam no testpaths (busca robusta, sem ancora fragil)."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTAS = ["tests", "core", "api", "gestao", "plataforma", "vitrine", "governanca", "rede",
          "fase8_tests", "documentos", "midia", "relacionamento", "busca", "acesso", "cobranca", "fiscal"]

caminho = RAIZ / "pyproject.toml"
texto = caminho.read_text(encoding="utf-8")
encontrado = re.search(r"testpaths = \[(.*?)\]", texto, re.S)
if encontrado is None:
    raise SystemExit("ERRO: nao achei a linha testpaths")

atual = [item.strip().strip('"') for item in encontrado.group(1).split(",") if item.strip()]
final = atual + [pasta for pasta in PASTAS if pasta not in atual]
substituicao = "testpaths = [" + ", ".join(f'"{pasta}"' for pasta in final) + "]"
texto = texto[:encontrado.start()] + substituicao + texto[encontrado.end():]
caminho.write_text(texto, encoding="utf-8")

conferido = re.search(r"testpaths = \[(.*?)\]", caminho.read_text(encoding="utf-8"), re.S)
declaradas = [item.strip().strip('"') for item in conferido.group(1).split(",") if item.strip()]
faltando = [pasta for pasta in PASTAS if pasta not in declaradas]
if faltando:
    raise SystemExit(f"ERRO: testpaths sem {faltando}")
print("testpaths:", ", ".join(declaradas))
# confere que cada pasta declarada existe
ausentes = [pasta for pasta in declaradas if not (RAIZ / pasta).is_dir()]
if ausentes:
    raise SystemExit(f"ERRO: testpaths aponta para pasta inexistente: {ausentes}")
print("todas as pastas do testpaths existem")
