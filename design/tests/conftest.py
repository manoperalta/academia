"""Fixtures da vitrine do design system."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, VinculoUsuario
from core.papeis import Papel

SENHA = "SenhaForteDesign!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Design", slug="academia-design", status="ativo")


@pytest.fixture
def cliente_painel(client, db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.design", password=SENHA, email="admin.design@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    client.force_login(usuario)
    return client
