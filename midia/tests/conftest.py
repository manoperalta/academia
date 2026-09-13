"""Fixtures do app de midia."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from usuarios.models import Usuario

SENHA = "SenhaForteMidia!23"


@pytest.fixture(autouse=True)
def media_temporaria(tmp_path, settings):
    """Nada de escrever no MEDIA_ROOT de verdade durante os testes."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Midia", slug="academia-midia", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Outra Academia", slug="outra-midia", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.midia", password=SENHA, email="admin.midia@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.midia", password=SENHA, email="aluno.midia@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno da Midia", status_user="Ativo"
    )


@pytest.fixture
def aula(db, rede, admin_do_painel):
    from aulas.models import Aulas

    return Aulas.todos.create(
        rede=rede,
        nome="Aula de forca",
        descricao="Treino guiado",
        professor=admin_do_painel,
        categorias_exercicios="forca",
    )
