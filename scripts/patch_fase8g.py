#!/usr/bin/env python3
"""Fase 8g: inclui os testes da fase 8 na suite padrao (testpaths)."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = (
    'testpaths = ["tests", "core", "api", "gestao", "plataforma", "vitrine", "governanca", "rede"]'
)
NOVO = 'testpaths = ["tests", "core", "api", "gestao", "plataforma", "vitrine", "governanca", "rede", "fase8_tests"]'

caminho = RAIZ / "pyproject.toml"
texto = caminho.read_text(encoding="utf-8")
if '"fase8_tests"' in texto:
    print("pyproject: fase8_tests ja esta na suite")
elif ALVO in texto:
    caminho.write_text(texto.replace(ALVO, NOVO, 1), encoding="utf-8")
    print("pyproject: fase8_tests incluido na suite padrao")
else:
    raise SystemExit("ERRO: nao achei o testpaths esperado")

if '"fase8_tests"' not in caminho.read_text(encoding="utf-8"):
    raise SystemExit("ERRO: testpaths nao recebeu a pasta da fase 8")
print("patch fase 8g concluido")
