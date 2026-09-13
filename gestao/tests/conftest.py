"""Fixtures do painel (Fase 2)."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import VinculoUsuario
from core.papeis import Papel
from usuarios.models import Usuario


def _pessoa(username: str, **extra):
    return get_user_model().objects.create_user(
        username=username, password="senha-de-teste-123",
        email=f"{username}@exemplo.com", **extra
    )


@pytest.fixture
def admin_rede(db, usuario, rede, unidade, vinculo_admin):
    """Usuario com papel de administrador da rede (ve todas as unidades)."""
    return usuario


@pytest.fixture
def recepcionista(db, rede, unidade):
    pessoa = _pessoa("recepcao.teste")
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.RECEPCAO
    )
    return pessoa


@pytest.fixture
def professor_user(db, rede, unidade):
    pessoa = _pessoa("professor.teste", is_professor=True)
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.PROFESSOR
    )
    return pessoa


@pytest.fixture
def aluno_user(db, rede, unidade):
    pessoa = _pessoa("aluno.teste", is_student=True)
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.ALUNO
    )
    return pessoa


@pytest.fixture
def sem_vinculo(db):
    return _pessoa("sem.vinculo")


@pytest.fixture
def cliente_recepcao(db, recepcionista):
    cliente = Client()
    cliente.force_login(recepcionista)
    return cliente


@pytest.fixture
def cliente_professor(db, professor_user):
    cliente = Client()
    cliente.force_login(professor_user)
    return cliente


@pytest.fixture
def cliente_aluno(db, aluno_user):
    cliente = Client()
    cliente.force_login(aluno_user)
    return cliente


@pytest.fixture
def cliente_sem_vinculo(db, sem_vinculo):
    cliente = Client()
    cliente.force_login(sem_vinculo)
    return cliente


@pytest.fixture
def aluno_da_rede(db, rede, unidade, usuario):
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=usuario, nome="Aluno Um",
        email_user="aluno.um@exemplo.com", telefone_user="51999990000",
        status_user="Ativo",
    )
