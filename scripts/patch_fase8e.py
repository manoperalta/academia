#!/usr/bin/env python3
"""Fase 8e: zera o lint (convencao N818 e dois ajustes pontuais). Roda dentro do container."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def patch_pyproject() -> None:
    caminho = RAIZ / "pyproject.toml"
    texto = caminho.read_text(encoding="utf-8")
    if '"N818"' not in texto:
        ancora = '    "RUF012", # ClassVar em models do Django e ruido'
        if ancora not in texto:
            raise SystemExit("ERRO: nao achei a lista ignore do ruff")
        texto = texto.replace(
            ancora,
            ancora + '\n    "N818",   # convencao do projeto: excecoes em pt-BR (ErroDeX)',
            1,
        )
        caminho.write_text(texto, encoding="utf-8")
    if '"N818"' not in caminho.read_text(encoding="utf-8"):
        raise SystemExit("ERRO: N818 nao entrou no ignore")
    print("pyproject: N818 ignorado (convencao pt-BR de nomes de excecao)")


def patch_importacao() -> None:
    caminho = RAIZ / "gestao" / "importacao.py"
    texto = caminho.read_text(encoding="utf-8")
    alvo = '_status(valor, "Ativo" if tipo == "alunos" else "Ativo")'
    if alvo in texto:
        caminho.write_text(texto.replace(alvo, '_status(valor, "Ativo")', 1), encoding="utf-8")
        print("importacao: condicao if/else sem efeito removida")
    else:
        print("importacao: nada a corrigir")


def patch_form() -> None:
    import django

    django.setup()
    from rede.models import PoliticaDaRede

    campos = [
        campo.name
        for campo in PoliticaDaRede._meta.fields
        if campo.name not in {"rede", "atualizado_em"}
    ]
    caminho = RAIZ / "rede" / "forms.py"
    texto = caminho.read_text(encoding="utf-8")
    alvo = '        exclude = ["rede", "atualizado_em"]'
    if alvo in texto:
        if texto.count(alvo) != 1:
            raise SystemExit("ERRO: mais de um exclude igual em rede/forms.py")
        novo = (
            "        fields = [\n"
            + "".join(f'            "{nome}",\n' for nome in campos)
            + "        ]"
        )
        caminho.write_text(texto.replace(alvo, novo, 1), encoding="utf-8")
        print(f"rede/forms.py: fields explicito com {len(campos)} campo(s) no lugar de exclude")
    else:
        print("rede/forms.py: nada a corrigir")


if __name__ == "__main__":
    patch_pyproject()
    patch_importacao()
    patch_form()
    print("patch fase 8e concluido")
