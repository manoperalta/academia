"""Navegacao e saida dos paineis.

Guarda contra a regressao que apareceu em 14/09/2026: o painel de gestao
mandava o usuario para ``/accounts/logout/`` por GET e o ``LogoutView`` do
Django 5 so aceita POST, entao "Sair" devolvia 405 (erro ao sair da gestao).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import Unidade, VinculoUsuario
from core.papeis import Papel

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


# ------------------------------------------------------- painel de gestao x dashboard


def test_navegacao_mostra_o_painel_para_quem_tem_permissao(cliente_logado):
    """Ate 14/09/2026 nao havia nenhum caminho de navegacao para /gestao/."""
    html = cliente_logado.get(reverse("dashboard")).content.decode()
    assert reverse("gestao:visao_geral") in html
    assert "Painel de gestão" in html


def test_dashboard_da_equipe_oferece_o_botao_do_painel():
    """Alem do item da navbar, o card do dashboard da equipe traz o atalho.

    Nao da para checar por requisicao: o superusuario sem 2FA e desviado pelo
    ``DoisFatosMiddleware`` (a resposta vem vazia), entao o guarda e no template.
    """
    html = (Path(settings.BASE_DIR) / "dashboard/templates/dashboard/dashboard.html").read_text(
        encoding="utf-8"
    )
    assert "Abrir painel de gestão da academia" in html
    assert "{% url 'gestao:visao_geral' %}" in html


def test_aluno_nao_ve_a_entrada_do_painel(db, rede, unidade):
    aluno = get_user_model().objects.create_user(
        username="aluno.painel", password="senha-de-teste-123", is_student=True
    )
    VinculoUsuario.todos.create(usuario=aluno, rede=rede, unidade=unidade, papel=Papel.ALUNO)
    cliente = Client()
    cliente.force_login(aluno)
    resposta = cliente.get(reverse("dashboard"))
    assert resposta.status_code == 200
    assert reverse("gestao:visao_geral") not in resposta.content.decode()


def test_painel_tem_atalho_de_volta_para_o_dashboard(cliente_logado):
    html = cliente_logado.get(reverse("gestao:visao_geral")).content.decode()
    assert reverse("dashboard") in html
    assert "Dashboard da academia" in html


def test_seletor_de_unidade_aparece_no_dashboard_com_duas_unidades(
    db, cliente_logado, rede, unidade
):
    Unidade.todos.create(rede=rede, nome="Unidade Filial", codigo="filial")
    html = cliente_logado.get(reverse("dashboard")).content.decode()
    assert "Todas as unidades" in html
    assert "Unidade Filial" in html


def test_seletor_de_unidade_nao_aparece_com_uma_unidade(cliente_logado):
    html = cliente_logado.get(reverse("dashboard")).content.decode()
    assert "Todas as unidades" not in html


def test_seletor_do_painel_lista_as_unidades(cliente_logado, unidade):
    """O select existia mas iterava ``unidades_disponiveis`` que ninguem fornecia."""
    html = cliente_logado.get(reverse("gestao:visao_geral")).content.decode()
    assert "Todas as unidades" in html
    assert unidade.nome in html


def test_troca_de_unidade_grava_na_sessao_e_volta_para_o_dashboard(
    db, cliente_logado, unidade
):
    resposta = cliente_logado.post(
        reverse("gestao:selecionar_unidade"),
        {"unidade": str(unidade.pk), "voltar": reverse("dashboard")},
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("dashboard")
    assert cliente_logado.session["unidade_id"] == unidade.pk
