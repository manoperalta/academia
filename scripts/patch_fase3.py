#!/usr/bin/env python3
"""Fase 3: liga o painel da plataforma ao projeto (idempotente e verificado)."""
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
    if '\n    "plataforma",' in texto:
        print("settings: plataforma ja registrado")
        return
    novo, trocas = re.subn(
        r'(LOCAIS = \[\s*\n\s*"core",)', r'\1\n    "plataforma",', texto, count=1
    )
    if trocas == 0:
        raise SystemExit("ERRO: LOCAIS nao encontrado em base.py")
    _verificar(novo, '"plataforma"', "settings_env/base.py")
    caminho.write_text(novo, encoding="utf-8")
    print("settings: app plataforma registrado")


def patch_urls() -> None:
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "plataforma.urls" in texto:
        print("urls: rota /plataforma/ ja existe")
        return
    padrao = re.compile(
        r"^(?P<indent>\s*)path\(\s*[\'\"]admin/[\'\"]\s*,\s*admin\.site\.urls\s*\),\s*$",
        re.MULTILINE,
    )
    novo, trocas = padrao.subn(
        lambda m: f'{m.group("indent")}path("admin/", admin.site.urls),\n'
                  f'{m.group("indent")}path("plataforma/", include("plataforma.urls")),',
        texto,
        count=1,
    )
    if trocas == 0:
        raise SystemExit("ERRO: linha do admin nao encontrada em app/urls.py")
    _verificar(novo, "plataforma.urls", "app/urls.py")
    caminho.write_text(novo, encoding="utf-8")
    print("urls: rota /plataforma/ adicionada e verificada")


def patch_pyproject() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"plataforma"' in texto:
        print("pyproject: plataforma ja citado")
        return
    novo, trocas = re.subn(
        r'(testpaths\s*=\s*\[)([^\]]*)(\])',
        lambda m: f'{m.group(1)}{m.group(2)}, "plataforma"{m.group(3)}',
        texto,
        count=1,
    )
    if trocas == 0:
        print("pyproject: testpaths nao encontrado (nada a fazer)")
        return
    _verificar(novo, '"plataforma"', "pyproject.toml")
    caminho.write_text(novo, encoding="utf-8")
    print("pyproject: plataforma adicionado aos testpaths")


def patch_tenancy() -> None:
    """O resolvedor passa a respeitar a impersonation da sessao."""
    caminho = RAIZ / "core" / "tenancy.py"
    texto = caminho.read_text(encoding="utf-8")
    if "_impersonacao_da_sessao" in texto:
        print("tenancy: impersonation ja considerada")
        return
    antigo = (
        "    rede, unidade = _da_sessao(request)\n"
        "    if rede:\n"
        "        return rede, unidade\n"
    )
    novo = (
        "    rede, unidade = _da_sessao(request)\n"
        "    if rede:\n"
        "        return rede, unidade\n"
        "\n"
        "    # Suporte: sessao com impersonation ativa entra na visao do cliente.\n"
        "    impersonacao = _impersonacao_da_sessao(request)\n"
        "    if impersonacao is not None:\n"
        "        return impersonacao.rede, None\n"
    )
    if antigo not in texto:
        raise SystemExit("ERRO: trecho da sessao nao encontrado em core/tenancy.py")
    texto = texto.replace(antigo, novo, 1)
    texto = texto.rstrip("\n") + "\n\n\n" + (
        "def _impersonacao_da_sessao(request):\n"
        '    """Impersonation ativa na sessao (import tardio evita ciclo com a plataforma)."""\n'
        '    if not hasattr(request, "session"):\n'
        "        return None\n"
        '    identificador = request.session.get("impersonacao_id")\n'
        "    if not identificador:\n"
        "        return None\n"
        "    from plataforma.models import Impersonacao\n"
        "\n"
        "    return Impersonacao.objects.filter(pk=identificador, fim__isnull=True).first()\n"
    )
    _verificar(texto, "_impersonacao_da_sessao(request)", "core/tenancy.py")
    caminho.write_text(texto, encoding="utf-8")
    print("tenancy: resolvedor respeita impersonation")


def patch_mixins() -> None:
    """Vinculo de rede nao e exigido durante impersonation (equipe da plataforma)."""
    caminho = RAIZ / "core" / "mixins.py"
    texto = caminho.read_text(encoding="utf-8")
    if "impersonando_suporte" in texto:
        print("mixins: impersonation ja considerada")
        return
    antigo = (
        "            if not papeis and not request.user.is_superuser:\n"
        '                raise PermissionDenied("Voce nao tem vinculo com esta academia.")\n'
    )
    novo = (
        "            if not papeis and not request.user.is_superuser and not impersonando_suporte(request):\n"
        '                raise PermissionDenied("Voce nao tem vinculo com esta academia.")\n'
    )
    if antigo not in texto:
        raise SystemExit("ERRO: trecho do vinculo nao encontrado em core/mixins.py")
    texto = texto.replace(antigo, novo, 1)
    if "def impersonando_suporte" not in texto:
        linhas = texto.splitlines(keepends=True)
        ultimo = 0
        for indice, linha in enumerate(linhas[:60]):
            if linha.startswith("import ") or linha.startswith("from "):
                ultimo = indice
        linhas.insert(ultimo + 1, (
            "\n\ndef impersonando_suporte(request) -> bool:\n"
            '    """True quando a requisicao esta dentro de um acesso de suporte auditado."""\n'
            '    if not hasattr(request, "session"):\n'
            "        return False\n"
            '    return bool(request.session.get("impersonacao_id"))\n'
        ))
        texto = "".join(linhas)
    _verificar(texto, "impersonando_suporte(request)", "core/mixins.py")
    caminho.write_text(texto, encoding="utf-8")
    print("mixins: impersonation libera o acesso do suporte")


def patch_apoio_tests() -> None:
    """O teste generico de isolamento passa a ignorar o app plataforma (agrega entre tenants)."""
    caminho = RAIZ / "tests" / "apoio.py"
    texto = caminho.read_text(encoding="utf-8")
    if '"plataforma"' in texto:
        print("apoio.py: plataforma ja ignorado")
        return
    antigo = '"auth", "admin", "sessions", "contenttypes", "core"'
    novo = '"auth", "admin", "sessions", "contenttypes", "core", "plataforma"'
    if antigo not in texto:
        raise SystemExit("ERRO: lista de apps ignorados nao encontrada em tests/apoio.py")
    texto = texto.replace(antigo, novo, 1)
    if '"plataforma"' not in texto:
        raise SystemExit("ERRO: patch de tests/apoio.py nao aplicou")
    caminho.write_text(texto, encoding="utf-8")
    print("apoio.py: app plataforma ignorado no teste generico (tem teste proprio de isolamento)")


if __name__ == "__main__":
    patch_settings()
    patch_urls()
    patch_pyproject()
    patch_tenancy()
    patch_mixins()
    patch_apoio_tests()
    print("patch fase 3 concluido")
