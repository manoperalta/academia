"""Fixtures do portal do aluno."""

from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade
from financeiro.models import Plano
from painel.models import Painel
from usuarios.models import Usuario

SENHA = "SenhaFortePortal!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Portal", slug="academia-portal", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Vizinha", slug="vizinha-portal", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.portal", password=SENHA, email="aluno.portal@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluna Portal", status_user="Ativo"
    )


@pytest.fixture
def cliente_aluno(client, aluno):
    client.force_login(aluno.user)
    return client


@pytest.fixture
def responsavel(db):
    """Painel exige responsavel; aqui e so o dono da turma."""
    return get_user_model().objects.create_user(username="dono.turma", password=SENHA)


@pytest.fixture
def turma(rede, unidade, responsavel):
    return Painel.objects.create(
        rede=rede,
        unidade=unidade,
        nome="Turma das 19h",
        data=timezone.localdate() + timedelta(days=2),
        hora_inicio=time(19, 0),
        hora_fim=time(20, 0),
        numero_de_user=2,
        responsavel=responsavel,
    )


@pytest.fixture
def plano(rede, unidade):
    return Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal", tipo="mensal", valor=Decimal("199.00")
    )
