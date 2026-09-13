"""Fixtures da fase 8 (comissoes, gamificacao, NPS e area do aluno)."""

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
from usuarios.models import Usuario

SENHA = "SenhaForteFase8!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Academia Fase 8", slug="academia-fase8", status="ativo")


@pytest.fixture
def unidade(db, rede):
    return Unidade.objects.create(
        rede=rede,
        nome="Centro",
        codigo="centro",
        tipo="propria",
        cidade="Montenegro",
        uf="RS",
        status="ativa",
    )


@pytest.fixture
def professor(db, rede, unidade):
    return Professor.todos.create(
        rede=rede, unidade=unidade, nome="Prof. Teste", status_prof="Ativo"
    )


@pytest.fixture
def aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.fase8", password=SENHA, email="aluno.fase8@x.com"
    )
    perfil = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Teste", status_user="Ativo"
    )
    return perfil


@pytest.fixture
def receita(db, rede, unidade, aluno):
    """Receita recebida no mes para a comissao percentual."""
    hoje = timezone.localdate()
    plano = Plano.objects.create(
        rede=rede, unidade=unidade, nome="Mensal", tipo="mensal", valor=Decimal("200.00")
    )
    for posicao in range(2):
        login = get_user_model().objects.create_user(
            username=f"pagante{posicao}", password=SENHA, email=f"pag{posicao}@x.com"
        )
        Usuario.todos.create(
            rede=rede, unidade=unidade, user=login, nome=f"Pagante {posicao}", status_user="Ativo"
        )
        Pagamento.objects.create(
            rede=rede,
            unidade=unidade,
            usuario=login,
            plano=plano,
            valor_pago=Decimal("200.00"),
            data_pagamento=hoje,
            data_inicio=hoje,
            data_fim=hoje + timedelta(days=30),
            status="pago",
        )
    return plano


@pytest.fixture
def admin_do_painel(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.fase8", password=SENHA, email="admin.fase8@x.com"
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario
