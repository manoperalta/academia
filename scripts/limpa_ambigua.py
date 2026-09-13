#!/usr/bin/env python3
"""Troca o sinal de multiplicacao ambiguo (x unicode) pelo x latino em um arquivo."""

from __future__ import annotations

import sys
from pathlib import Path

caminho = Path(sys.argv[1])
texto = caminho.read_text(encoding="utf-8")
if "\u00d7" not in texto:
    print(f"{caminho}: nada a trocar")
    sys.exit(0)
caminho.write_text(texto.replace("\u00d7", "x"), encoding="utf-8")
print(f"{caminho}: trocado")
