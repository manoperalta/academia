#!/usr/bin/env python3
"""Fase 6: monta as rotas da rede na raiz (/gestao/rede/...) para o namespace ser 'rede'."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    gestao = RAIZ / "gestao" / "urls.py"
    texto = gestao.read_text(encoding="utf-8")
    if 'include("rede.urls")' in texto:
        texto = texto.replace('    path("rede/", include("rede.urls")),\n', "", 1)
        if 'include("rede.urls")' in texto:
            raise SystemExit("ERRO: nao removi o include aninhado")
        gestao.write_text(texto, encoding="utf-8")
        print("gestao/urls.py: include aninhado removido")
    else:
        print("gestao/urls.py: nada a remover")

    app = RAIZ / "app" / "urls.py"
    texto = app.read_text(encoding="utf-8")
    if "rede.urls" in texto:
        print("app/urls.py: rede ja montado")
        return
    ancora = '    path("gestao/", include("gestao.urls")),'
    if ancora not in texto:
        raise SystemExit("ERRO: include do gestao nao encontrado em app/urls.py")
    texto = texto.replace(ancora, '    path("gestao/rede/", include("rede.urls")),\n' + ancora, 1)
    if "rede.urls" not in texto:
        raise SystemExit("ERRO: rede nao entrou em app/urls.py")
    app.write_text(texto, encoding="utf-8")
    print("app/urls.py: /gestao/rede/ -> rede.urls (namespace rede)")


if __name__ == "__main__":
    main()
