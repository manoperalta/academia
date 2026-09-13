"""Fixtures da conta e do suporte."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from usuarios.models import Usuario

SENHA = "SenhaForteConta!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Conta", slug="academia-conta", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Alheia", slug="alheia-conta", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.conta", password=SENHA, email="admin.conta@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.conta", password=SENHA, email="aluno.conta@x.com"
    )
    VinculoUsuario.todos.create(
        usuario=login, rede=rede, unidade=unidade, papel=Papel.ALUNO, ativo=True
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Conta", status_user="Ativo"
    )


@pytest.fixture
def cliente_equipe(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client


@pytest.fixture
def cliente_aluno(client, aluno):
    client.force_login(aluno.user)
    return client
