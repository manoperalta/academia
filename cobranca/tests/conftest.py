"""Fixtures da cobranca recorrente."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from usuarios.models import Usuario

SENHA = "SenhaForteCobranca!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Cobranca", slug="academia-cobranca", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(
        nome="Academia Alheia Cobranca", slug="alheia-cobranca", status="ativo"
    )


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def plano(db, rede, unidade):
    return Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("199.00")
    )


@pytest.fixture
def aluno(db, rede, unidade, plano):
    login = get_user_model().objects.create_user(
        username="aluno.cobranca", password=SENHA, email="aluno.cobranca@x.com"
    )
    perfil = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Cobranca", status_user="Ativo"
    )
    hoje = timezone.localdate()
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=login,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje - timedelta(days=30),
        data_fim=hoje,
        status="pago",
    )
    return perfil


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.cobranca", password=SENHA, email="admin.cobranca@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client
