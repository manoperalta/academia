"""Fixtures dos documentos de negocio."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from professores.models import Professor
from remuneracao.models import RegraDeComissao, TipoDeComissao
from remuneracao.servicos import apurar_competencia
from usuarios.models import Usuario

SENHA = "SenhaForteDocumentos!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Peralta", slug="academia-documentos", status="ativo")


@pytest.fixture
def outra_rede(db):
    return Rede.todos.create(
        nome="Academia Concorrente", slug="concorrente-documentos", status="ativo"
    )


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(
        rede=rede,
        nome="Unidade Centro",
        codigo="centro",
        tipo="propria",
        cnpj="12.345.678/0001-90",
        endereco="Rua das Acacias, 100",
        cidade="Montenegro",
        uf="RS",
        telefone="51 3632-0000",
        status="ativa",
    )


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.documentos", password=SENHA, email="aluno.documentos@x.com"
    )
    return Usuario.todos.create(
        rede=rede,
        unidade=unidade,
        user=login,
        nome="João Conceição da Silva",
        status_user="Ativo",
    )


@pytest.fixture
def professor(db, rede, unidade):
    return Professor.todos.create(
        rede=rede, unidade=unidade, nome="Prof. Teste", status_prof="Ativo"
    )


@pytest.fixture
def plano(db, rede, unidade):
    return Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("199.00")
    )


@pytest.fixture
def pagamento(db, rede, unidade, aluno, plano):
    hoje = timezone.localdate()
    return Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("189.05"),
        data_pagamento=hoje,
        data_inicio=hoje,
        data_fim=hoje + timedelta(days=30),
        status="pago",
    )


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.documentos", password=SENHA, email="admin.documentos@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def apuracao(db, rede, unidade, professor, pagamento):
    """Apuracao de comissao real, pelo proprio servico da fase 8."""
    RegraDeComissao.objects.create(
        rede=rede,
        professor=professor,
        tipo=TipoDeComissao.PERCENTUAL,
        percentual=Decimal("10.000"),
        piso_mensal=Decimal("50.00"),
    )
    apurar_competencia(rede)
    from remuneracao.models import ApuracaoDeComissao

    return ApuracaoDeComissao.objects.get()


@pytest.fixture
def cliente_painel(client, admin_do_painel):
    client.force_login(admin_do_painel)
    return client


@pytest.fixture
def cliente_restrito(client, db, rede, unidade):
    """Papel sem acesso a financeiro: serve para provar o 403 do painel."""
    login = get_user_model().objects.create_user(
        username="recepcao.documentos", password=SENHA, email="recepcao.documentos@x.com"
    )
    VinculoUsuario.todos.create(
        usuario=login, rede=rede, unidade=unidade, papel=Papel.PROFESSOR, ativo=True
    )
    client.force_login(login)
    return client


@pytest.fixture
def repasse(db, rede, unidade):
    """Repasse com os campos reais do modelo (base, percentual, fundo, piso, hash)."""
    from rede.models import Repasse

    hoje = timezone.localdate()
    return Repasse.objects.create(
        rede=rede,
        unidade=unidade,
        inicio=hoje.replace(day=1),
        fim=hoje,
        base="liquido",
        receita_bruta=Decimal("720.00"),
        exclusoes=Decimal("18.00"),
        receita_liquida=Decimal("702.00"),
        base_de_calculo=Decimal("702.00"),
        percentual=Decimal("8.000"),
        fundo_de_marketing=Decimal("1.50"),
        valor_do_royalty=Decimal("56.16"),
        valor_do_fundo=Decimal("10.53"),
        valor_devido=Decimal("66.69"),
        piso_aplicado=False,
        vencimento=hoje + timedelta(days=5),
        hash_do_calculo="8934b0ee36f0be61a1f2cd98",
        observacoes="Conferido linha a linha pela unidade.",
    )
