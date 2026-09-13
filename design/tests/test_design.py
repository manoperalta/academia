"""Testes do design system: a vitrine abre e os componentes renderizam."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_vitrine_abre(cliente_painel):
    resposta = cliente_painel.get(reverse("design:vitrine"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Design system" in corpo
    assert "ds-selo" in corpo and "ds-tabela" in corpo


def test_arquivo_de_tokens_existe():
    from django.conf import settings

    caminho = Path(settings.BASE_DIR) / "design" / "static" / "design" / "tokens.css"
    assert caminho.is_file()
    conteudo = caminho.read_text(encoding="utf-8")
    assert "--cor-marca" in conteudo and "--raio" in conteudo


def test_selo_respeita_o_tom():
    html = render_to_string("design/components/selo.html", {"texto": "liberado", "tom": "sucesso"})
    assert "ds-selo-sucesso" in html and "liberado" in html


def test_kpi_mostra_rotulo_valor_e_detalhe():
    html = render_to_string(
        "design/components/kpi.html",
        {"rotulo": "Vendas", "valor": "R$ 100,00", "detalhe": "3 vendas"},
    )
    assert "Vendas" in html and "R$ 100,00" in html and "3 vendas" in html


def test_alerta_sem_texto_nao_renderiza_nada():
    html = render_to_string("design/components/alerta.html", {})
    assert "ds-alerta" not in html


def test_estado_vazio_com_acao():
    html = render_to_string(
        "design/components/estado_vazio.html",
        {"titulo": "Nada aqui", "acao_url": "/x/", "acao_texto": "Ir"},
    )
    assert "Nada aqui" in html and 'href="/x/"' in html


def test_paginacao_so_aparece_com_mais_de_uma_pagina():
    from django.core.paginator import Paginator

    paginas = Paginator(list(range(5)), 2)
    html_uma_pagina = render_to_string(
        "design/components/paginacao.html", {"page_obj": paginas.page(1), "paginator": paginas}
    )
    paginas_pequenas = Paginator(list(range(3)), 10)
    html_unica = render_to_string(
        "design/components/paginacao.html",
        {"page_obj": paginas_pequenas.page(1), "paginator": paginas_pequenas},
    )
    assert "Próxima" in html_uma_pagina
    assert "ds-paginacao" not in html_unica


def test_progresso_usa_o_valor_recebido():
    html = render_to_string("design/components/progresso.html", {"valor": 42, "rotulo": "quase"})
    assert "width: 42%" in html and "quase" in html
