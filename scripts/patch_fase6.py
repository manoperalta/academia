#!/usr/bin/env python3
"""Fase 6: liga o app rede (settings, rotas do painel, testpaths). Idempotente."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def patch_settings():
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if '\n    "rede",' in texto:
        print("settings: rede ja registrado")
        return
    novo, trocas = re.subn(r'(LOCAIS = \[\s*\n\s*"core",)', r'\1\n    "rede",', texto, count=1)
    if trocas == 0:
        raise SystemExit("ERRO: LOCAIS nao encontrado")
    if '\n    "rede",' not in novo:
        raise SystemExit("ERRO: rede nao entrou no LOCAIS")
    caminho.write_text(novo, encoding="utf-8")
    print("settings: app rede registrado")


def patch_pyproject():
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"rede"' in texto:
        print("pyproject: rede ja citado")
        return
    novo, trocas = re.subn(r'(testpaths\s*=\s*\[)([^\]]*)(\])',
                           lambda m: m.group(1) + m.group(2) + ', "rede"' + m.group(3), texto, count=1)
    if trocas:
        caminho.write_text(novo, encoding="utf-8")
        print("pyproject: rede nos testpaths")
    else:
        print("pyproject: testpaths nao encontrado")


def patch_apoio():
    caminho = RAIZ / "tests" / "apoio.py"
    if not caminho.exists():
        print("tests/apoio.py nao encontrado")
        return
    texto = caminho.read_text(encoding="utf-8")
    if '"rede"' in texto:
        print("apoio: rede ja ignorado")
        return
    novo, trocas = re.subn(r'(\n\s*"governanca",)(\n\s*"plataforma",)', r'\1"rede",\2', texto, count=1)
    if trocas == 0:
        novo, trocas = re.subn(r'("governanca",)', r'"governanca", "rede",', texto, count=1)
    if trocas:
        caminho.write_text(novo, encoding="utf-8")
        print("apoio: rede marcado como app de plataforma")
    else:
        print("apoio: conjunto de apps nao encontrado")


if __name__ == "__main__":
    patch_settings()
    patch_pyproject()
    patch_apoio()
    print("patch fase 6 concluido")
