#!/usr/bin/env python3
"""Fase 8: modelos filhos (sem rede propria) entram na lista de ignorados do teste de isolamento."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FILHOS = ("remuneracao.itemdecomissao", "gamificacao.lancamentodepontos",
          "gamificacao.conquistadoaluno", "nps.resposta")


def main() -> None:
    caminho = RAIZ / "tests" / "apoio.py"
    texto = caminho.read_text(encoding="utf-8")
    faltando = [item for item in FILHOS if item not in texto]
    if not faltando:
        print("apoio: filhos da fase 8 ja ignorados")
        return
    alvo = "ignorados = {"
    if alvo not in texto:
        raise SystemExit("ERRO: conjunto ignorados nao encontrado")
    inserir = "\n".join(f'        "{item}",' for item in FILHOS)
    texto = texto.replace(alvo, alvo + "\n" + inserir, 1)
    for item in FILHOS:
        if item not in texto:
            raise SystemExit(f"ERRO: {item} nao entrou")
    caminho.write_text(texto, encoding="utf-8")
    print("apoio: filhos da fase 8 escopados pelo pai")


if __name__ == "__main__":
    main()
