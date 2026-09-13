#!/usr/bin/env python3
"""Anexa a auditoria da plataforma e o comparativo de unidades aos apps existentes."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
IMPORTES = {
    "plataforma/views.py": "from plataforma.views_auditoria import AuditoriaDaPlataformaView  # noqa: E402, F401",
    "rede/views.py": "from rede.views_comparativo import ComparativoDeUnidadesView  # noqa: E402, F401",
}
ROTAS = {
    "plataforma/urls.py": (
        '    path("auditoria/", views.AuditoriaDaPlataformaView.as_view(), name="auditoria"),',
        "AuditoriaDaPlataformaView",
    ),
    "rede/urls.py": (
        '    path("comparativo/", views.ComparativoDeUnidadesView.as_view(), name="comparativo"),',
        "ComparativoDeUnidadesView",
    ),
}


def anexar_importe(caminho: Path, linha: str, marcador: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marcador in texto:
        print(f"{caminho.name}: importe ja presente")
        return
    caminho.write_text(texto.rstrip() + chr(10) + chr(10) + linha + chr(10), encoding="utf-8")
    if marcador not in caminho.read_text(encoding="utf-8"):
        raise SystemExit(f"ERRO: importe nao entrou em {caminho}")
    print(f"{caminho.name}: importe anexado")


def anexar_rota(caminho: Path, linha: str, marcador: str) -> None:
    texto = caminho.read_text(encoding="utf-8")
    if marcador in texto:
        print(f"{caminho.name}: rota ja existe")
        return
    posicao = texto.rstrip().rfind("]")
    if posicao == -1:
        raise SystemExit(f"ERRO: nao achei o fim das rotas de {caminho}")
    caminho.write_text(texto[:posicao] + linha + chr(10) + texto[posicao:], encoding="utf-8")
    if marcador not in caminho.read_text(encoding="utf-8"):
        raise SystemExit(f"ERRO: rota nao entrou em {caminho}")
    print(f"{caminho.name}: rota anexada")


if __name__ == "__main__":
    for arquivo, linha in IMPORTES.items():
        anexar_importe(RAIZ / arquivo, linha, linha.split()[-2])
    for arquivo, (linha, marcador) in ROTAS.items():
        anexar_rota(RAIZ / arquivo, linha, marcador)
    print("telas finais anexadas")
