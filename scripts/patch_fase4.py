#!/usr/bin/env python3
"""Fase 4: liga o site publico ao projeto (idempotente e verificado)."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _verificar(texto: str, marca: str, arquivo: str) -> None:
    if marca not in texto:
        raise SystemExit(f"ERRO: patch nao aplicou em {arquivo} (faltou {marca!r})")


def patch_settings() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if '"vitrine"' in texto:
        print("settings: vitrine ja registrado")
        return
    novo, trocas = re.subn(r'(LOCAIS = \[\s*\n\s*"core",)', r'\1\n    "vitrine",', texto, count=1)
    if trocas == 0:
        raise SystemExit("ERRO: LOCAIS nao encontrado em base.py")
    _verificar(novo, '"vitrine"', "settings_env/base.py")
    caminho.write_text(novo, encoding="utf-8")
    print("settings: app vitrine registrado")


def patch_urls() -> None:
    """O site publico passa a responder na raiz; a landing antiga vai para /academia/."""
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "vitrine.urls" in texto:
        print("urls: vitrine ja na raiz")
        return
    padrao = re.compile(
        r"^(?P<indent>\s*)path\(\s*[\'\"][\'\"]\s*,\s*academia_views\.index\s*,"
        r"\s*name=[\'\"]index[\'\"]\s*\),\s*$",
        re.MULTILINE,
    )
    novo, trocas = padrao.subn(
        lambda m: (
            f'{m.group("indent")}path("", include("vitrine.urls")),\n'
            f'{m.group("indent")}path("academia/", academia_views.index, name="index"),'
        ),
        texto,
        count=1,
    )
    if trocas == 0:
        raise SystemExit("ERRO: linha da landing antiga nao encontrada em app/urls.py")
    _verificar(novo, "vitrine.urls", "app/urls.py")
    _verificar(novo, 'name="index"', "app/urls.py")
    caminho.write_text(novo, encoding="utf-8")
    print("urls: vitrine na raiz e landing antiga em /academia/")


def patch_pyproject() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"vitrine"' in texto:
        print("pyproject: vitrine ja citado")
        return
    novo, trocas = re.subn(
        r"(testpaths\s*=\s*\[)([^\]]*)(\])",
        lambda m: f'{m.group(1)}{m.group(2)}, "vitrine"{m.group(3)}',
        texto,
        count=1,
    )
    if trocas == 0:
        print("pyproject: testpaths nao encontrado (nada a fazer)")
        return
    _verificar(novo, '"vitrine"', "pyproject.toml")
    caminho.write_text(novo, encoding="utf-8")
    print("pyproject: vitrine adicionado aos testpaths")


def patch_email_de_teste() -> None:
    """Garante o backend locmem nos testes (permite inspecionar mail.outbox)."""
    caminho = RAIZ / "app" / "settings_env" / "test.py"
    texto = caminho.read_text(encoding="utf-8")
    if "locmem.EmailBackend" in texto:
        print("test settings: backend de e-mail ja e locmem")
        return
    texto = texto.rstrip("\n") + (
        "\n\n# E-mails ficam em django.core.mail.outbox durante os testes.\n"
        'EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"\n'
    )
    _verificar(texto, "locmem.EmailBackend", "settings_env/test.py")
    caminho.write_text(texto, encoding="utf-8")
    print("test settings: backend de e-mail locmem")


if __name__ == "__main__":
    patch_settings()
    patch_urls()
    patch_pyproject()
    patch_email_de_teste()
    print("patch fase 4 concluido")
