"""Fixtures compartilhadas (pytest-django)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.context import limpar_contexto
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel


@pytest.fixture(autouse=True)
def contexto_limpo():
    """Nenhum teste herda contexto de rede do teste anterior (thread-local)."""
    limpar_contexto()
    yield
    limpar_contexto()


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Teste", slug="teste")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Outra Academia", slug="outra")


@pytest.fixture
def unidade(db, rede):
    return Unidade.todos.create(rede=rede, nome="Unidade Centro", codigo="centro")


@pytest.fixture
def unidade_da_outra_rede(db, outra_rede):
    return Unidade.todos.create(rede=outra_rede, nome="Unidade Filial", codigo="filial")


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user(
        username="admin.teste", password="senha-de-teste-123", email="admin@exemplo.com"
    )


@pytest.fixture
def vinculo_admin(db, usuario, rede, unidade):
    return VinculoUsuario.todos.create(
        usuario=usuario, rede=rede, unidade=unidade, papel=Papel.ADMIN_REDE
    )


@pytest.fixture
def cliente_logado(db, usuario, vinculo_admin):
    cliente = Client()
    cliente.force_login(usuario)
    return cliente
