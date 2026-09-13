#!/usr/bin/env python3
"""Fase 8: registra os apps novos (remuneracao, gamificacao, nps, area_do_aluno)."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APPS = ("remuneracao", "gamificacao", "nps", "area_do_aluno")


def patch_settings() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if '"area_do_aluno",' in texto:
        print("settings: apps da fase 8 ja registrados")
        return
    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas):
        if linha.strip() == '"rede",':
            linhas[indice + 1:indice + 1] = [f'    "{app}",' for app in APPS]
            break
    else:
        raise SystemExit("ERRO: nao achei a lista LOCAIS no settings")
    texto = "\n".join(linhas) + "\n"
    for app in APPS:
        if f'"{app}",' not in texto:
            raise SystemExit(f"ERRO: {app} nao entrou nas INSTALLED_APPS")
    caminho.write_text(texto, encoding="utf-8")
    print("settings: " + ", ".join(APPS))


def patch_urls() -> None:
    caminho = RAIZ / "app" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "area_do_aluno.urls" in texto:
        print("urls: ja montado")
        return
    rotas = [
        "    path(\"gestao/remuneracao/\", include(\"remuneracao.urls\")),",
        "    path(\"gestao/gamificacao/\", include(\"gamificacao.urls\")),",
        "    path(\"gestao/nps/\", include(\"nps.urls\")),",
        "    path(\"aluno/\", include(\"area_do_aluno.urls\")),",
    ]
    marcador = "urlpatterns = ["
    if marcador not in texto:
        raise SystemExit("ERRO: urlpatterns nao encontrado")
    texto = texto.replace(marcador, marcador + "\n" + "\n".join(rotas), 1)
    if "area_do_aluno.urls" not in texto:
        raise SystemExit("ERRO: rotas da fase 8 nao entraram")
    if "from django.urls import include" not in texto:
        texto = texto.replace("from django.urls import path",
                              "from django.urls import include, path", 1)
    if "from django.urls import include" not in texto:
        raise SystemExit("ERRO: include nao importado em app/urls.py")
    caminho.write_text(texto, encoding="utf-8")
    print("urls: remuneracao, gamificacao, nps e area do aluno")


def patch_permissoes() -> None:
    caminho = RAIZ / "gestao" / "permissoes.py"
    texto = caminho.read_text(encoding="utf-8")
    if "COMISSOES" in texto:
        print("permissoes: modulos ja existem")
        return
    alvo = '    PRIVACIDADE = "privacidade", "Privacidade e LGPD"'
    if alvo not in texto:
        raise SystemExit("ERRO: nao achei o enum de modulos")
    texto = texto.replace(alvo, alvo + "\n"
                          + '    COMISSOES = "comissoes", "Comissoes e remuneracao"\n'
                          + '    GAMIFICACAO = "gamificacao", "Gamificacao"\n'
                          + '    PESQUISAS = "pesquisas", "Pesquisas e NPS"', 1)
    alvo_papel = '        Modulo.PRIVACIDADE: "ver",'
    if alvo_papel not in texto:
        raise SystemExit("ERRO: nao achei a matriz do gestor de unidade")
    texto = texto.replace(alvo_papel, alvo_papel + "\n"
                          + '        Modulo.COMISSOES: "ver",\n'
                          + '        Modulo.GAMIFICACAO: "ver",\n'
                          + '        Modulo.PESQUISAS: "ver",', 1)
    caminho.write_text(texto, encoding="utf-8")
    print("permissoes: modulos registrados")


def patch_menu() -> None:
    caminho = RAIZ / "gestao" / "menu.py"
    texto = caminho.read_text(encoding="utf-8")
    if "remuneracao:regras" in texto:
        print("menu: ja aponta para as telas novas")
        return
    alvo = '    Modulo.PRIVACIDADE: "gestao:privacidade",'
    if alvo not in texto:
        raise SystemExit("ERRO: nao achei o mapa de rotas do menu")
    texto = texto.replace(alvo, alvo + "\n"
                          + '    Modulo.COMISSOES: "remuneracao:regras",\n'
                          + '    Modulo.GAMIFICACAO: "gamificacao:regras",\n'
                          + '    Modulo.PESQUISAS: "nps:pesquisas",', 1)
    if "remuneracao:regras" not in texto:
        raise SystemExit("ERRO: menu nao recebeu as rotas novas")
    caminho.write_text(texto, encoding="utf-8")
    print("menu: comissoes, gamificacao e pesquisas")


if __name__ == "__main__":
    patch_settings()
    patch_urls()
    patch_permissoes()
    patch_menu()
    print("patch fase 8 concluido")
