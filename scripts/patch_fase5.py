#!/usr/bin/env python3
"""Fase 5: liga o app governanca, o 2FA, a midia protegida e o log com contexto. Idempotente."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _confere(texto, marcas, arquivo):
    for marca in marcas:
        if marca not in texto:
            raise SystemExit(f"ERRO: patch nao aplicou em {arquivo} (faltou {marca!r})")


def patch_settings():
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")

    if '"governanca"' not in texto:
        novo, trocas = re.subn(r'(LOCAIS = \[\s*\n\s*"core",)', r'\1\n    "governanca",', texto, count=1)
        if trocas == 0:
            raise SystemExit("ERRO: LOCAIS nao encontrado")
        texto = novo
        _confere(texto, ['"governanca"'], "settings_env/base.py")

    if 'MEDIA_URL = "/midia/"' not in texto:
        novo, trocas = re.subn(r'^MEDIA_URL = .*$', 'MEDIA_URL = "/midia/"', texto, count=1, flags=re.MULTILINE)
        if trocas == 0:
            raise SystemExit("ERRO: MEDIA_URL nao encontrado")
        texto = novo

    if "BACKUP_DIR" not in texto:
        texto = texto.rstrip("\n") + (
            '\n\n# Pasta dos backups do banco e das exportacoes por cliente (RNF-005)\n'
            'BACKUP_DIR = BASE_DIR / "backups"\n'
        )

    if "governanca.middleware.DoisFatoresMiddleware" not in texto:
        linhas = [
            '    "governanca.middleware.DoisFatoresMiddleware",',
            '    "governanca.middleware.MetricasMiddleware",',
        ]
        achou = re.search(r'^\s*["\']core\.middleware\.ResolucaoDeTenantMiddleware["\'],?\s*$',
                          texto, re.MULTILINE)
        if achou:
            fim = texto.index("\n", achou.end()) + 1
            texto = texto[:fim] + "\n".join(linhas) + "\n" + texto[fim:]
        else:
            fim_lista = re.search(r'^MIDDLEWARE = \[(.*?)^\]', texto, re.MULTILINE | re.DOTALL)
            if not fim_lista:
                raise SystemExit("ERRO: MIDDLEWARE nao encontrado")
            texto = texto[:fim_lista.end() - 1] + "\n".join(linhas) + "\n" + texto[fim_lista.end() - 1:]
        _confere(texto, ["governanca.middleware.DoisFatoresMiddleware",
                         "governanca.middleware.MetricasMiddleware"], "settings_env/base.py")

    if "FiltroDeContextoDeLog" not in texto:
        texto = texto.rstrip("\n") + (
            '\n\n# Log com contexto do cliente e do usuario em cada linha (RNF-008)\n'
            'LOGGING = {\n'
            '    "version": 1,\n'
            '    "disable_existing_loggers": False,\n'
            '    "filters": {"contexto": {"()": "governanca.middleware.FiltroDeContextoDeLog"}},\n'
            '    "formatters": {\n'
            '        "com_contexto": {"format": "%(asctime)s %(levelname)s tenant=%(tenant)s '
            'user=%(usuario)s %(name)s %(message)s"},\n'
            '    },\n'
            '    "handlers": {\n'
            '        "console": {"class": "logging.StreamHandler", "filters": ["contexto"], '
            '"formatter": "com_contexto"},\n'
            '    },\n'
            '    "root": {"handlers": ["console"], "level": "INFO"},\n'
            '}\n'
        )
        _confere(texto, ["FiltroDeContextoDeLog"], "settings_env/base.py")

    caminho.write_text(texto, encoding="utf-8")
    print("settings: governanca, midia protegida, middlewares e log com contexto")


def patch_logging():
    """Integra o filtro de contexto ao LOGGING existente (nao cria um segundo dicionario)."""
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")

    duplicado = "\n\n# Log com contexto do cliente e do usuario em cada linha (RNF-008)\nLOGGING = {"
    if duplicado in texto:
        inicio = texto.index(duplicado)
        fim = texto.index("\n}\n", inicio) + 3
        texto = texto[:inicio] + "\n" + texto[fim:]

    if '"contexto"' not in texto:
        alvo_filtro = '        "rede": {"()": "core.logging_filters.FiltroRede"},'
        if alvo_filtro in texto:
            texto = texto.replace(
                alvo_filtro,
                alvo_filtro + '\n        "contexto": {"()": "governanca.middleware.FiltroDeContextoDeLog"},',
                1,
            )
        alvo_handler = '            "filters": ["rede"],'
        if alvo_handler in texto:
            texto = texto.replace(alvo_handler, '            "filters": ["rede", "contexto"],', 1)
        alvo_formato = '"format": "[{asctime}] {levelname} {name} rede={rede_id} {message}"'
        if alvo_formato in texto:
            texto = texto.replace(
                alvo_formato,
                '"format": "[{asctime}] {levelname} {name} rede={rede_id} user={usuario} {message}"',
                1,
            )
        caminho.write_text(texto, encoding="utf-8")

    final = caminho.read_text(encoding="utf-8")
    if final.count("\nLOGGING = {") > 1:
        raise SystemExit("ERRO: ainda existem dois blocos LOGGING")
    _confere(final, ['"contexto"'], "settings_env/base.py")
    print("logging: filtro de contexto integrado ao log existente (com o usuario na linha)")


def patch_urls():
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "governanca.urls" in texto:
        print("urls: governanca ja registrado")
        return
    marca = '    path("", include("vitrine.urls")),'
    if marca not in texto:
        raise SystemExit("ERRO: include da vitrine nao encontrado")
    texto = texto.replace(marca, marca + '\n    path("", include("governanca.urls")),', 1)
    _confere(texto, ["governanca.urls"], "app/urls.py")
    caminho.write_text(texto, encoding="utf-8")
    print("urls: governanca registrado")


CORPO_DO_HOST = (
    '    # Subdominio do cliente ou dominio proprio (RF-PLT-050)\n'
    '    try:\n'
    '        from governanca.servicos import rede_por_host\n'
    '\n'
    '        host = request.get_host()\n'
    '    except Exception:  # noqa: BLE001 - host desconhecido cai no fluxo normal\n'
    '        host = ""\n'
    '    if host:\n'
    '        rede_do_host = rede_por_host(host)\n'
    '        if rede_do_host is not None:\n'
    '            return rede_do_host\n'
)


def patch_tenancy():
    caminho = RAIZ / "core" / "tenancy.py"
    texto = caminho.read_text(encoding="utf-8")
    if "rede_por_host" in texto:
        print("tenancy: resolucao por host ja aplicada")
        return
    padrao = re.compile(
        r'(def resolver_rede\(request\):\s*\n(?:\s*"""[\s\S]*?"""\s*\n)?)'
    )
    novo, trocas = padrao.subn(lambda achado: achado.group(1) + CORPO_DO_HOST, texto, count=1)
    if trocas == 0:
        raise SystemExit("ERRO: resolver_rede nao encontrada")
    _confere(novo, ["rede_por_host"], "core/tenancy.py")
    caminho.write_text(novo, encoding="utf-8")
    print("tenancy: resolucao por host aplicada")


def patch_pyproject():
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"governanca"' in texto:
        print("pyproject: governanca ja citado")
        return
    novo, trocas = re.subn(r'(testpaths\s*=\s*\[)([^\]]*)(\])',
                           lambda m: m.group(1) + m.group(2) + ', "governanca"' + m.group(3), texto, count=1)
    if trocas == 0:
        print("pyproject: testpaths nao encontrado")
        return
    _confere(novo, ['"governanca"'], "pyproject.toml")
    caminho.write_text(novo, encoding="utf-8")
    print("pyproject: governanca nos testpaths")


def patch_apoio_de_testes():
    caminho = RAIZ / "tests" / "apoio.py"
    if not caminho.exists():
        print("tests/apoio.py nao encontrado (nada a fazer)")
        return
    texto = caminho.read_text(encoding="utf-8")
    if '"governanca"' in texto:
        print("apoio de testes: governanca ja ignorado")
        return
    novo, trocas = re.subn(r'("contenttypes",\s*"core")', r'"contenttypes", "core", "governanca"', texto, count=1)
    if trocas == 0:
        novo, trocas = re.subn(r'("core")', r'"core", "governanca"', texto, count=1)
    if trocas == 0:
        print("apoio de testes: conjunto de apps nao encontrado (nada a fazer)")
        return
    _confere(novo, ['"governanca"'], "tests/apoio.py")
    caminho.write_text(novo, encoding="utf-8")
    print("apoio de testes: governanca marcado como app de plataforma")


if __name__ == "__main__":
    patch_settings()
    patch_logging()
    patch_urls()
    patch_tenancy()
    patch_pyproject()
    patch_apoio_de_testes()
    print("patch fase 5 concluido")
