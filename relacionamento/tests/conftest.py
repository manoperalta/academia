"""Fixtures do CRM e da retencao."""

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

SENHA = "SenhaForteCrm!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia CRM", slug="academia-crm", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Vizinha", slug="academia-vizinha", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(rede=rede, nome="Unidade Centro", codigo="centro", tipo="propria")


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.crm", password=SENHA, email="admin.crm@x.com"
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
        username="aluno.crm", password=SENHA, email="aluno.crm@x.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Teste", status_user="Ativo"
    )


@pytest.fixture
def plano(db, rede, unidade):
    return Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("199.00")
    )


def pagar(rede, unidade, aluno, plano, *, vence_em: int):
    """Pagamento com vencimento deslocado em dias (negativo = vencido)."""
    hoje = timezone.localdate()
    return Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje + timedelta(days=vence_em - 30),
        data_fim=hoje + timedelta(days=vence_em),
        status="pago",
    )


def treinar(aluno, unidade, *, dias_atras: int):
    from area_do_aluno.models import CheckinDoAluno

    entrada = CheckinDoAluno.objects.create(rede=aluno.rede, aluno=aluno, unidade=unidade)
    CheckinDoAluno.objects.filter(pk=entrada.pk).update(
        criado_em=timezone.now() - timedelta(days=dias_atras)
    )
    return entrada


def responder_detrator(aluno, rede, unidade):
    from nps.models import Pesquisa, Resposta, TipoDePesquisa

    pesquisa = Pesquisa.objects.create(
        rede=rede,
        unidade=unidade,
        titulo="Pos-aula",
        pergunta="De 0 a 10, quanto voce indica?",
        tipo=TipoDePesquisa.NPS,
    )
    return Resposta.objects.create(
        pesquisa=pesquisa,
        aluno=aluno,
        unidade=unidade,
        nota=3,
        comentario="Nao me senti bem atendido.",
    )
