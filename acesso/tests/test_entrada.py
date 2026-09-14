"""Tela de entrada depois do login (por onde o dono continua)."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from acesso.entrada import EscolherPainelView, operador_da_plataforma


def test_login_manda_para_a_tela_de_entrada(db):
    assert settings.LOGIN_REDIRECT_URL == "acesso:entrada"
    assert reverse("acesso:entrada") == "/entrada/"


def test_usuario_de_rede_vai_direto_para_a_academia(cliente_logado):
    """Quem tem vinculo em uma rede nao passa pela escolha: cai no ambiente da rede."""
    resposta = cliente_logado.get(reverse("acesso:entrada"))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("dashboard")


def test_operador_da_plataforma_e_reconhecido():
    novo = get_user_model()
    assert operador_da_plataforma(novo(is_superuser=True)) is True
    assert operador_da_plataforma(novo(is_staff=True)) is True
    assert operador_da_plataforma(novo()) is False


def test_destinos_do_dono_incluem_plataforma_painel_e_dashboard(db, rede):
    dono = get_user_model().objects.create_superuser(
        username="dono.entrada", email="dono.entrada@exemplo.com", password="senha-de-teste-123"
    )
    pedido = RequestFactory().get("/entrada/")
    pedido.user = dono
    pedido.rede = rede
    pedido.unidade = None
    visao = EscolherPainelView()
    visao.request = pedido
    visao.args = ()
    visao.kwargs = {}
    rotas = [item["rota"] for item in visao.destinos()]
    assert reverse("plataforma:metricas") in rotas
    assert reverse("gestao:visao_geral") in rotas
    assert reverse("dashboard") in rotas
