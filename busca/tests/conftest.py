"""Fixtures da busca."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from usuarios.models import Usuario

SENHA = "SenhaForteBusca!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Busca", slug="academia-busca", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(nome="Academia Alheia", slug="academia-alheia", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(
        rede=rede,
        nome="Unidade Central",
        codigo="central",
        tipo="propria",
        cidade="Montenegro",
        uf="RS",
    )


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="maria.buscavel", password=SENHA, email="maria@exemplo.com"
    )
    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Maria Buscavel", status_user="Ativo"
    )


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.busca", password=SENHA, email="admin.busca@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def professor_do_painel(db, rede, unidade):
    usuario = get_user_model().objects.create_user(
        username="prof.busca", password=SENHA, email="prof.busca@x.com"
    )
    VinculoUsuario.todos.create(
        usuario=usuario, rede=rede, unidade=unidade, papel=Papel.PROFESSOR, ativo=True
    )
    return usuario


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client


@pytest.fixture
def cliente_professor(client, professor_do_painel):
    client.force_login(professor_do_painel)
    return client


@pytest.fixture
def cenario_buscavel(db, rede, unidade, aluno):
    """Um item de cada fonte, todos contendo o termo 'maria'."""
    from midia import servicos as servicos_de_midia
    from relacionamento import servicos as servicos_de_crm

    plano = Plano.objects.create(
        rede=rede, unidade=unidade, nome="Plano Maria", tipo="mensal", valor=Decimal("199.00")
    )
    from datetime import timedelta

    from django.utils import timezone

    hoje = timezone.localdate()
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje,
        data_fim=hoje + timedelta(days=30),
        status="pago",
    )
    lead = servicos_de_crm.registrar_lead(
        rede=rede, unidade=unidade, nome="Maria Lead", telefone="51999990000"
    )
    servicos_de_crm.atualizar_perfis_de_risco(rede)
    arquivo = servicos_de_midia.iniciar_envio(
        rede=rede,
        titulo="Video da Maria",
        nome_original="maria.mp4",
        tamanho=100,
        tipo="video",
        unidade=unidade,
    )
    return {"aluno": aluno, "lead": lead, "arquivo": arquivo, "plano": plano}
