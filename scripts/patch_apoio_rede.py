#!/usr/bin/env python3
"""Acrescenta o app 'rede' ao conjunto de apps de plataforma nos testes de isolamento."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ALVO = RAIZ / "tests" / "apoio.py"


def main() -> None:
    texto = ALVO.read_text(encoding="utf-8")
    if '\n            "rede",' in texto:
        print("apoio: rede ja listado")
        return
    marcador = '            "plataforma",\n'
    if marcador not in texto:
        raise SystemExit("ERRO: conjunto de apps nao encontrado")
    texto = texto.replace(marcador, marcador + '            "rede",\n', 1)
    if '\n            "rede",' not in texto:
        raise SystemExit("ERRO: rede nao entrou")
    ALVO.write_text(texto, encoding="utf-8")
    print("apoio: app rede marcado como plataforma (entidades de rede com FK explicita)")


if __name__ == "__main__":
    main()
