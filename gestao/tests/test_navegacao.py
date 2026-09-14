"""Navegacao e saida dos paineis.

Guarda contra a regressao que apareceu em 14/09/2026: o painel de gestao
mandava o usuario para ``/accounts/logout/`` por GET e o ``LogoutView`` do
Django 5 so aceita POST, entao "Sair" devolvia 405 (erro ao sair da gestao).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

# Layouts que oferecem a saida: (rotulo, caminho relativo ao BASE_DIR)
LAYOUTS = (
    ("app antigo", "templates/base.html"),
    ("painel de gestao", "gestao/templates/gestao/base.html"),
    ("area do professor", "painel_do_professor/templates/professor/base.html"),
    ("minha conta", "conta/templates/conta/base.html"),
)


def _ler(caminho: str) -> str:
    return (Path(settings.BASE_DIR) / caminho).read_text(encoding="utf-8")


@pytest.mark.parametrize(("rotulo", "caminho"), LAYOUTS)
def test_layout_oferece_saida_por_post(rotulo, caminho):
    html = _ler(caminho)
    assert 'action="{% url \'logout\' %}"' in html or 'action="/accounts/logout/"' in html, (
        f"o layout '{rotulo}' nao oferece saida"
    )
    trecho = html[max(0, html.find("logout") - 300) : html.find("logout") + 400]
    assert "method=\"post\"" in trecho, f"o layout '{rotulo}' precisa sair por POST"
    assert "{% csrf_token %}" in trecho, f"o formulario de saida de '{rotulo}' sem csrf"


def test_nenhum_layout_usa_link_get_para_sair():
    alvos = [caminho for _, caminho in LAYOUTS]
    for caminho in alvos:
        assert 'href="/accounts/logout/"' not in _ler(caminho), (
            f"{caminho} voltou a usar link GET para sair (405 no Django 5)"
        )


def test_logout_por_get_e_recusado(db, client):
    """Documenta o motivo do ajuste: GET nao encerra sessao no Django 5."""
    assert client.get(reverse("logout")).status_code == 405


def test_logout_por_post_encerra_a_sessao(cliente_logado):
    assert cliente_logado.get(reverse("gestao:visao_geral")).status_code == 200
    resposta = cliente_logado.post(reverse("logout"))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("login")
    assert cliente_logado.get(reverse("gestao:visao_geral")).status_code == 302


def test_painel_de_gestao_sai_por_formulario_post(cliente_logado):
    html = cliente_logado.get(reverse("gestao:visao_geral")).content.decode()
    assert 'action="/accounts/logout/"' in html
    assert 'href="/accounts/logout/"' not in html
