"""Testes de caracterizacao: congelam o comportamento atual antes da refatoracao.

Objetivo (Fase 0 do PRD): nenhuma tela pode passar de "funciona" para "500".
Nao afirmam que a tela esta bonita ou correta -- afirmam que ela nao quebrou.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.caracterizacao

#: Rotas publicas e internas do sistema atual (app/urls.py).
ROTAS = [
    "/",
    "/accounts/",
    "/dashboard/",
    "/aulas/",
    "/agendamento/",
    "/usuarios/",
    "/professores/",
    "/painel/",
    "/financeiro/",
    "/relatorios/",
    "/notificacoes/",
    "/api/v1/estado/",
    "/api/docs/",
    "/api/schema/",
]

STATUS_ACEITOS = {200, 301, 302, 303, 403, 404, 405}


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_rota_nao_quebra_anonimo(cliente_anonimo, rota):
    resposta = cliente_anonimo.get(rota)
    assert resposta.status_code in STATUS_ACEITOS, f"{rota} -> {resposta.status_code}"
    assert resposta.status_code < 500


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ROTAS)
def test_rota_nao_quebra_logado(cliente_logado, rota):
    resposta = cliente_logado.get(rota)
    assert resposta.status_code in STATUS_ACEITOS, f"{rota} -> {resposta.status_code}"
    assert resposta.status_code < 500


@pytest.mark.django_db
def test_admin_continua_acessivel_para_staff(cliente_anonimo, usuario):
    usuario.is_staff = True
    usuario.is_superuser = True
    usuario.save()
    cliente_anonimo.force_login(usuario)
    resposta = cliente_anonimo.get("/admin/")
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_login_por_senha_cria_sessao(cliente_anonimo):
    get_user_model().objects.create_user(username="aluno.teste", password="senha-forte-123")
    assert cliente_anonimo.login(username="aluno.teste", password="senha-forte-123") is True
    resposta = cliente_anonimo.get("/dashboard/")
    assert resposta.status_code < 500


@pytest.mark.django_db
def test_estado_da_instalacao_responde_sem_autenticacao(cliente_anonimo):
    resposta = cliente_anonimo.get("/api/v1/estado/")
    assert resposta.status_code == 200
    assert resposta.json()["versao_api"] == "1.0.0"


@pytest.fixture
def cliente_anonimo():
    from django.test import Client

    return Client()
