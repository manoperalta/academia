"""Fixtures do fiscal."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from fiscal import servicos
from usuarios.models import Usuario

SENHA = "SenhaForteFiscal!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Fiscal", slug="academia-fiscal", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Alheia Fiscal", slug="alheia-fiscal", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def plano(db, rede, unidade):
    return Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("200.00")
    )


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.fiscal", password=SENHA, email="aluno.fiscal@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Fiscal", status_user="Ativo"
    )


@pytest.fixture
def pagamento(db, rede, unidade, aluno, plano):
    hoje = timezone.localdate()
    return Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("200.00"),
        data_inicio=hoje.replace(day=1),
        data_fim=hoje.replace(day=1) + timedelta(days=30),
        status="pago",
    )


@pytest.fixture
def configuracao(rede):
    return servicos.configurar_fiscal(
        rede=rede,
        regime="simples",
        municipio="Montenegro",
        inscricao_municipal="12345",
        codigo_do_servico="6.01",
        aliquota_iss=Decimal("5.00"),
        provedor="simulado",
        retem_pis_cofins_csll=False,
        retem_ir=False,
        retem_inss=False,
    )


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.fiscal", password=SENHA, email="admin.fiscal@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client
