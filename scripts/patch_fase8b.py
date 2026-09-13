#!/usr/bin/env python3
"""Fase 8b: fecha o que faltou (enum de modulos, matriz do gestor e modelos de plataforma)."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODULOS = ('    COMISSOES = "comissoes", "Comissoes e remuneracao"\n'
           '    GAMIFICACAO = "gamificacao", "Gamificacao"\n'
           '    PESQUISAS = "pesquisas", "Pesquisas e NPS"')

PARENTES_E_FILHOS = ("remuneracao.regradecomissao", "remuneracao.apuracaodecomissao",
                     "remuneracao.itemdecomissao", "gamificacao.regradepontos",
                     "gamificacao.saldodepontos", "gamificacao.lancamentodepontos",
                     "gamificacao.conquista", "gamificacao.conquistadoaluno", "nps.pesquisa",
                     "nps.resposta", "area_do_aluno.checkindoaluno")


def patch_permissoes() -> None:
    caminho = RAIZ / "gestao" / "permissoes.py"
    texto = caminho.read_text(encoding="utf-8")
    if "COMISSOES" not in texto:
        ancora = '    CATALOGO = "catalogo", "Catalogo da rede"'
        if ancora not in texto:
            ancora = '    CATALOGO = "catalogo", "Catálogo da rede"'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei o fim do enum de modulos")
        texto = texto.replace(ancora, ancora + "\n" + MODULOS, 1)
        if "COMISSOES" not in texto:
            raise SystemExit("ERRO: modulo COMISSOES nao entrou no enum")
    if 'Modulo.COMISSOES: "ver"' not in texto:
        ancora = '        Modulo.PRIVACIDADE: "ver",'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei a matriz do gestor de unidade")
        texto = texto.replace(ancora, ancora + '\n'
                              + '        Modulo.COMISSOES: "ver",\n'
                              + '        Modulo.GAMIFICACAO: "ver",\n'
                              + '        Modulo.PESQUISAS: "ver",', 1)
    for exigido in ("COMISSOES", 'Modulo.COMISSOES', 'Modulo.GAMIFICACAO', 'Modulo.PESQUISAS'):
        if exigido not in texto:
            raise SystemExit(f"ERRO: {exigido} ausente em permissoes.py")
    caminho.write_text(texto, encoding="utf-8")
    print("permissoes: 3 modulos no enum e na matriz do gestor")


def patch_apoio() -> None:
    caminho = RAIZ / "tests" / "apoio.py"
    texto = caminho.read_text(encoding="utf-8")
    faltando = [item for item in PARENTES_E_FILHOS if f'"{item}"' not in texto]
    if not faltando:
        print("apoio: modelos da fase 8 ja ignorados")
        return
    ancora = "ignorados = {"
    if ancora not in texto:
        raise SystemExit("ERRO: conjunto ignorados nao encontrado")
    inserir = "\n".join(f'        "{item}",' for item in faltando)
    texto = texto.replace(ancora, ancora + "\n" + inserir, 1)
    for item in faltando:
        if f'"{item}"' not in texto:
            raise SystemExit(f"ERRO: {item} nao entrou em apoio.py")
    caminho.write_text(texto, encoding="utf-8")
    print(f"apoio: {len(faltando)} modelo(s) da fase 8 como entidades de rede/plataforma")


if __name__ == "__main__":
    patch_permissoes()
    patch_apoio()
    print("patch fase 8b concluido")
