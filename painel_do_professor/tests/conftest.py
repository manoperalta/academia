"""Fixtures compartilhadas de treino e professor."""

from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from agendamento.models import Agendamento
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from painel.models import Painel
from professores.models import Professor
from usuarios.models import FichaSaude, Usuario

SENHA = "SenhaForteTreino!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Treino", slug="academia-treino", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Vizinha", slug="academia-vizinha", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.treino", password=SENHA, email="aluno.treino@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Treino", status_user="Ativo"
    )


@pytest.fixture
def outro_aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="outro.treino", password=SENHA, email="outro.treino@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Outro Aluno", status_user="Ativo"
    )


@pytest.fixture
def professor(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="prof.treino", password=SENHA, email="prof.treino@x.com"
    )
    VinculoUsuario.todos.create(
        usuario=login, rede=rede, unidade=unidade, papel=Papel.PROFESSOR, ativo=True
    )
    return Professor.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Professor Treino", status_prof="Ativo"
    )


@pytest.fixture
def outro_professor(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="prof.dois", password=SENHA, email="prof.dois@x.com"
    )
    VinculoUsuario.todos.create(
        usuario=login, rede=rede, unidade=unidade, papel=Papel.PROFESSOR, ativo=True
    )
    return Professor.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Outro Professor", status_prof="Ativo"
    )


@pytest.fixture
def turma(db, rede, unidade, professor):
    return Painel.objects.create(
        rede=rede,
        unidade=unidade,
        nome="Turma das 7h",
        data=timezone.localdate(),
        hora_inicio=time(7, 0),
        hora_fim=time(8, 0),
        responsavel=professor.user,
        numero_de_user=12,
    )


@pytest.fixture
def agendamento(db, rede, unidade, turma, aluno):
    return Agendamento.objects.create(
        rede=rede,
        unidade=unidade,
        painel=turma,
        aluno=aluno.user,
        data_agendamento=timezone.now() + timedelta(days=1),
        status="pendente",
    )


@pytest.fixture
def ficha(db, rede, unidade, aluno):
    return FichaSaude.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno,
        altura=Decimal("1.75"),
        peso=Decimal("80.00"),
        restricoes="coluna,hipertensao",
        usa_medicamento=False,
    )


@pytest.fixture
def cliente_professor(client, professor):
    client.force_login(professor.user)
    return client


@pytest.fixture
def cliente_aluno(client, aluno):
    client.force_login(aluno.user)
    return client
