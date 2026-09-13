#!/usr/bin/env python3
"""Fase 8 (documentos): registra o app, monta as rotas e inclui os testes na suite."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def registrar_app() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if '"documentos"' in texto:
        print("settings: app documentos ja registrado")
        return
    ancora = '    "notificacoes",'
    if ancora not in texto:
        raise SystemExit("ERRO: nao achei a lista LOCAIS")
    texto = texto.replace(ancora, ancora + '\n    "documentos",', 1)
    caminho.write_text(texto, encoding="utf-8")
    if '"documentos"' not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: app documentos nao entrou em LOCAIS")
    print("settings: app documentos registrado")


def montar_rotas() -> None:
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "documentos.urls" in texto:
        print("urls: rotas dos documentos ja montadas")
        return
    ancora = 'path("", include("vitrine.urls")),'
    if ancora not in texto:
        raise SystemExit("ERRO: nao achei o ponto de montagem no app/urls.py")
    texto = texto.replace(ancora, ancora + '\n    path("", include("documentos.urls")),', 1)
    caminho.write_text(texto, encoding="utf-8")
    if "documentos.urls" not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: rotas dos documentos nao foram montadas")
    print("urls: rotas dos documentos montadas")


def incluir_testes() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"documentos"' in texto:
        print("pyproject: testes dos documentos ja na suite")
        return
    ancora = ', "fase8_tests"]'
    if ancora not in texto:
        raise SystemExit("ERRO: nao achei o testpaths da fase 8")
    texto = texto.replace(ancora, ', "fase8_tests", "documentos"]', 1)
    caminho.write_text(texto, encoding="utf-8")
    if '"documentos"]' not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: testpaths nao recebeu documentos")
    print("pyproject: testes dos documentos na suite padrao")


if __name__ == "__main__":
    registrar_app()
    montar_rotas()
    incluir_testes()
    print("patch documentos concluido")
