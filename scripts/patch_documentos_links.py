#!/usr/bin/env python3
"""Fase 8 (documentos): botoes de download nas telas, com ancora verificada."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ESTILO = 'class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"'

EDICOES = [
    (
        "gestao/templates/gestao/aluno_detalhe.html",
        "<a href=\"{% url 'gestao:aluno_editar' object.pk %}\" " + ESTILO + ">Editar cadastro</a>",
        lambda ancora: (
            ancora
            + "\n          <a href=\"{% url 'documentos:comprovante_de_matricula' object.pk %}\" "
            + ESTILO
            + ">Comprovante de matrícula</a>"
            + "\n          <a href=\"{% url 'documentos:carteirinha' object.pk %}\" "
            + ESTILO
            + ">Carteirinha</a>"
            + "\n          <a href=\"{% url 'documentos:contrato' object.pk %}\" "
            + ESTILO
            + ">Contrato de adesão</a>"
        ),
        "aluno_detalhe",
    ),
    (
        "rede/templates/rede/repasse_detalhe.html",
        '<a href="{% url \'rede:repasse_csv\' repasse.pk %}" class="rounded-lg border '
        'border-slate-300 px-4 py-2 text-sm">Baixar demonstrativo (CSV)</a>',
        lambda ancora: (
            ancora + "\n  <a href=\"{% url 'documentos:demonstrativo_de_repasse' repasse.pk %}\" "
            'class="rounded-lg border border-slate-300 px-4 py-2 text-sm">Baixar demonstrativo (PDF)</a>'
        ),
        "repasse_detalhe",
    ),
    (
        "remuneracao/templates/remuneracao/apuracao_detalhe.html",
        "{% block conteudo %}",
        lambda ancora: (
            ancora
            + '\n<div class="mx-auto max-w-4xl pb-2 text-right">'
            + "<a href=\"{% url 'documentos:extrato_de_comissao' apuracao.pk %}\" "
            + ESTILO
            + ">Baixar extrato (PDF)</a></div>"
        ),
        "apuracao_detalhe",
    ),
    (
        "area_do_aluno/templates/area_do_aluno/inicio.html",
        '<h1 id="ola" class="text-lg font-semibold">Ola, {{ aluno.nome }}</h1>',
        lambda ancora: (
            ancora + '\n  <p class="mt-1"><a class="text-sm text-sky-700 underline" '
            "href=\"{% url 'documentos:minha_carteirinha' %}\">Minha carteirinha (PDF)</a></p>"
        ),
        "pwa_inicio",
    ),
]


def aplicar() -> None:
    for relativo, ancora, montar, apelido in EDICOES:
        caminho = RAIZ / relativo
        if not caminho.exists():
            raise SystemExit(f"ERRO: {relativo} nao existe")
        texto = caminho.read_text(encoding="utf-8")
        if "documentos:" in texto:
            print(f"{apelido}: link dos documentos ja presente")
            continue
        if texto.count(ancora) != 1:
            raise SystemExit(f"ERRO: ancora de {apelido} nao e unica ({texto.count(ancora)})")
        texto = texto.replace(ancora, montar(ancora), 1)
        caminho.write_text(texto, encoding="utf-8")
        if "documentos:" not in caminho.read_text(encoding="utf-8"):
            raise SystemExit(f"ERRO: link nao entrou em {relativo}")
        print(f"{apelido}: botao de download adicionado")


if __name__ == "__main__":
    aplicar()
    print("patch links dos documentos concluido")
