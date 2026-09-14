"""Clientes por papel para as telas de integracao."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import VinculoUsuario
from core.papeis import Papel


def _pessoa(username: str, **extra):
    return get_user_model().objects.create_user(
        username=username, password="senha-de-teste-123", email=f"{username}@exemplo.com", **extra
    )


def _cliente(pessoa):
    cliente = Client()
    cliente.force_login(pessoa)
    return cliente


@pytest.fixture
def gestor_da_unidade(db, rede, unidade):
    pessoa = _pessoa("gestor.teste")
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.GESTOR_UNIDADE
    )
    return pessoa


@pytest.fixture
def cliente_gestor(db, gestor_da_unidade):
    return _cliente(gestor_da_unidade)


@pytest.fixture
def cliente_recepcao(db, rede, unidade):
    pessoa = _pessoa("recepcao.integracoes")
    VinculoUsuario.todos.create(usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.RECEPCAO)
    return _cliente(pessoa)


@pytest.fixture
def cliente_professor(db, rede, unidade):
    pessoa = _pessoa("professor.integracoes", is_professor=True)
    VinculoUsuario.todos.create(usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.PROFESSOR)
    return _cliente(pessoa)
