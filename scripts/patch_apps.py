#!/usr/bin/env python3
"""Registra apps novos do projeto: LOCAIS, rotas, testpaths e excecoes do teste de isolamento.

Idempotente e verificador: se a ancora nao existir, falha alto em vez de aplicar pela metade.
Para acrescentar um app, basta incluir o nome nas listas APPS/ROTAS/TESTPATHS/ISOLAMENTO.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

APPS: list[str] = ["midia", "relacionamento"]
ROTAS: list[str] = ["midia.urls", "relacionamento.urls"]
TESTPATHS: list[str] = ["midia"]
ISOLAMENTO: list[str] = [
    "midia.arquivodemidia", "midia.partedemidia",
    "relacionamento.lead", "relacionamento.interacaocomlead", "relacionamento.perfilderisco",
]


def registrar_apps() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    for app in APPS:
        if f'"{app}"' in texto:
            print(f"settings: {app} ja registrado")
            continue
        ancora = '    "documentos",'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei a lista LOCAIS")
        texto = texto.replace(ancora, ancora + f'\n    "{app}",', 1)
        print(f"settings: {app} registrado")
    caminho.write_text(texto, encoding="utf-8")
    conteudo = caminho.read_text(encoding="utf-8")
    for app in APPS:
        if f'"{app}"' not in conteudo:
            raise SystemExit(f"ERRO: {app} nao entrou em LOCAIS")


def montar_rotas() -> None:
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    for rota in ROTAS:
        if rota in texto:
            print(f"urls: {rota} ja montada")
            continue
        ancora = 'path("", include("documentos.urls")),'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei o ponto de montagem")
        texto = texto.replace(ancora, f'path("", include("{rota}")),\n    ' + ancora, 1)
        print(f"urls: {rota} montada")
    caminho.write_text(texto, encoding="utf-8")
    conteudo = caminho.read_text(encoding="utf-8")
    for rota in ROTAS:
        if rota not in conteudo:
            raise SystemExit(f"ERRO: {rota} nao montada")


def incluir_testes() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    for pasta in TESTPATHS:
        if f'"{pasta}"' in texto:
            print(f"pyproject: {pasta} ja na suite")
            continue
        ancora = ', "documentos"]'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei o testpaths")
        texto = texto.replace(ancora, f', "documentos", "{pasta}"]', 1)
        print(f"pyproject: {pasta} na suite padrao")
    caminho.write_text(texto, encoding="utf-8")


def marcar_isolamento() -> None:
    """Modelos que usam escopo explicito de rede entram na lista de excecoes do teste."""
    alvo = None
    for arquivo in (RAIZ / "tests").glob("*.py"):
        if "api.tarefaassincrona" in arquivo.read_text(encoding="utf-8"):
            alvo = arquivo
            break
    if alvo is None:
        raise SystemExit("ERRO: nao achei o arquivo com a lista de excecoes do isolamento")
    texto = alvo.read_text(encoding="utf-8")
    linhas = texto.splitlines()
    faltando = [modelo for modelo in ISOLAMENTO if f'"{modelo}"' not in texto]
    if not faltando:
        print("isolamento: modelos ja registrados")
        return
    inicio = next(i for i, linha in enumerate(linhas) if "api.tarefaassincrona" in linha)
    indentacao = re.match(r"\s*", linhas[inicio]).group(0)
    novas = [f'{indentacao}"{modelo}",' for modelo in faltando]
    for posicao, linha in enumerate(novas):
        linhas.insert(inicio + 1 + posicao, linha)
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"isolamento: {len(faltando)} modelo(s) marcados em {alvo.name}")


if __name__ == "__main__":
    registrar_apps()
    montar_rotas()
    incluir_testes()
    marcar_isolamento()
    print("patch de apps concluido")
