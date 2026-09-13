#!/usr/bin/env python3
"""Fase 8d: fecha o mapa de rotas do menu e garante que todo modulo tem rota.

O sintoma que isso corrige: um modulo presente em ``Modulo`` mas ausente de ``ROTAS``
faz o menu renderizar ``{% url "" %}`` e derruba TODAS as telas do painel com
NoReverseMatch. A checagem no fim deste script falha justamente para isso nao voltar.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

NOVAS = {
    "COMISSOES": '"remuneracao:regras"',
    "GAMIFICACAO": '"gamificacao:regras"',
    "PESQUISAS": '"nps:pesquisas"',
}


def patch_menu() -> None:
    caminho = RAIZ / "gestao" / "menu.py"
    texto = caminho.read_text(encoding="utf-8")
    if "remuneracao:regras" in texto:
        print("menu: rotas da fase 8 ja presentes")
    else:
        ancora = '    Modulo.AUDITORIA: "gestao:auditoria",'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei a ancora no mapa de rotas do menu")
        linhas = "".join(f"    Modulo.{nome}: {rota},\n" for nome, rota in NOVAS.items())
        texto = texto.replace(ancora, ancora + "\n" + linhas.rstrip("\n"), 1)
        caminho.write_text(texto, encoding="utf-8")
        print("menu: rotas de comissoes, gamificacao e pesquisas adicionadas")

    faltando = [nome for nome, rota in NOVAS.items() if rota not in caminho.read_text(encoding="utf-8")]
    if faltando:
        raise SystemExit(f"ERRO: rotas ausentes no menu: {faltando}")


def conferir_invariante() -> None:
    """Todo modulo do enum precisa ter rota, senao o menu quebra o painel inteiro."""
    import django

    django.setup()
    from gestao.menu import ROTAS
    from gestao.permissoes import Modulo

    sem_rota = [modulo.name for modulo in Modulo if modulo not in ROTAS]
    if sem_rota:
        raise SystemExit(f"ERRO: modulo sem rota no menu: {sem_rota}")
    print(f"menu: {len(ROTAS)} modulos mapeados, nenhum sem rota")


if __name__ == "__main__":
    patch_menu()
    conferir_invariante()
    print("patch fase 8d concluido")
