"""Fixtures da API v1 (fase 7)."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel

SENHA = "SenhaForteTeste123"


@pytest.fixture
def admin_da_rede_senha(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.api", password=SENHA, email="admin.api@academia.com.br")
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario, SENHA


@pytest.fixture
def receita(db, rede):
    """Alunos, plano e pagamentos para a API ter o que listar."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from financeiro.models import Pagamento, Plano
    from usuarios.models import Usuario

    hoje = timezone.localdate()
    unidade = Unidade.objects.create(rede=rede, nome="Unidade API", codigo="api", status="ativa")
    plano = Plano.objects.create(rede=rede, unidade=unidade, nome="Mensal API", tipo="mensal",
                                 valor=Decimal("150.00"))
    for posicao in range(3):
        login = get_user_model().objects.create_user(
            username=f"aluno.api.{posicao}", password=SENHA, email=f"api{posicao}@x.com")
        aluno = Usuario.todos.create(rede=rede, unidade=unidade, user=login,
                                     nome=f"Aluno API {posicao}", status_user="Ativo")
        Pagamento.objects.create(rede=rede, unidade=unidade, usuario=login, plano=plano,
                                 valor_pago=Decimal("150.00"), data_pagamento=hoje,
                                 data_inicio=hoje, data_fim=hoje + timedelta(days=30), status="pago")
    return {"unidade": unidade, "plano": plano}


@pytest.fixture
def outras_redes(db):
    """Outra rede com aluno proprio: o token de uma rede nao pode alcancar."""
    from usuarios.models import Usuario

    outra = Rede.todos.create(nome="Outra Academia", slug="outra-academia", status="ativo")
    login = get_user_model().objects.create_user(username="aluno.outra", password=SENHA,
                                                 email="outra@x.com")
    Usuario.todos.create(rede=outra, user=login, nome="Outra Aluna", status_user="Ativo")
    return [outra]
