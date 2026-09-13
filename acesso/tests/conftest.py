"""Fixtures do controle de acesso e dos parceiros."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from acesso import servicos as servicos_de_acesso
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from usuarios.models import Usuario

SENHA = "SenhaForteAcesso!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Acesso", slug="academia-acesso", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Alheia Acesso", slug="alheia-acesso", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def filial(db, rede):
    return Unidade.objects.create(
        rede=rede, nome="Unidade Zona Norte", codigo="zona-norte", tipo="franqueada"
    )


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.acesso", password=SENHA, email="aluno.acesso@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno do Acesso", status_user="Ativo"
    )


@pytest.fixture
def plano_em_dia(db, rede, unidade, aluno):

    hoje = timezone.localdate()
    plano = Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("199.00")
    )
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje,
        data_fim=hoje + timedelta(days=20),
        status="pago",
    )
    return plano


@pytest.fixture
def credencial(rede, aluno):
    return servicos_de_acesso.emitir_credencial(aluno=aluno, codigo="CARD-0001")


@pytest.fixture
def dispositivo(rede, unidade):
    from acesso.models import DispositivoDeAcesso

    return DispositivoDeAcesso.objects.create(
        rede=rede,
        unidade=unidade,
        nome="Catraca 1",
        tipo="catraca",
        identificador="catraca-1",
        token="token-de-teste-123",
    )


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.acesso", password=SENHA, email="admin.acesso@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client
