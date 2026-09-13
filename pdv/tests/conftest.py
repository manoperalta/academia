"""Fixtures do PDV."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from pdv import servicos
from usuarios.models import Usuario

SENHA = "SenhaFortePdv!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia PDV", slug="academia-pdv", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Alheia PDV", slug="alheia-pdv", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.pdv", password=SENHA, email="aluno.pdv@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno do PDV", status_user="Ativo"
    )


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.pdv", password=SENHA, email="admin.pdv@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client


@pytest.fixture
def produto(rede, unidade):
    return servicos.cadastrar_produto(
        rede=rede,
        unidade=unidade,
        nome="Whey 900g",
        preco_de_venda=Decimal("180.00"),
        custo=Decimal("120.00"),
        estoque_inicial=10,
        estoque_minimo=3,
    )
