"""Fixtures da rede (fase 6): tres unidades, alunos, planos e pagamentos."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from core.models import Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Plano
from usuarios.models import Usuario

SENHA = "SenhaForteTeste123"


@pytest.fixture
def unidades(db, rede):
    """Rede com 3 unidades operando (critério de saída da fase 6)."""
    return [
        Unidade.objects.create(rede=rede, nome=f"Unidade {nome}", codigo=nome.lower(), tipo=tipo,
                               cidade=cidade, uf="RS", status="ativa")
        for nome, tipo, cidade in (("Centro", "propria", "Montenegro"),
                                   ("Zona Sul", "franqueada", "Porto Alegre"),
                                   ("Serra", "franqueada", "Gramado"))
    ]


@pytest.fixture
def admin_da_rede(db, rede):
    usuario = get_user_model().objects.create_user(
        username="admin.rede", password=SENHA, email="admin@rede.com.br")
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    return usuario


@pytest.fixture
def cliente_rede(db, admin_da_rede):
    cliente = Client()
    cliente.force_login(admin_da_rede)
    return cliente


@pytest.fixture
def cliente_da_unidade(db, rede, unidades):
    usuario = get_user_model().objects.create_user(
        username="gestor.unidade", password=SENHA, email="gestor@unidade.com.br")
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, unidade=unidades[0],
                                papel=Papel.GESTOR_UNIDADE, ativo=True)
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


@pytest.fixture
def receita(db, rede, unidades):
    """Alunos, planos e pagamentos espalhados nas unidades, no mês corrente."""
    from financeiro.models import Pagamento

    hoje = timezone.localdate()
    plano = Plano.objects.create(rede=rede, unidade=unidades[0], nome="Mensal", tipo="mensal",
                                 valor=Decimal("150.00"))
    plano_rede = Plano.objects.create(rede=rede, unidade=None, nome="Mensal Rede", tipo="mensal",
                                      valor=Decimal("180.00"))
    dados = {"planos": [plano, plano_rede], "alunos": [], "pagamentos": []}
    for indice, unidade in enumerate(unidades):
        for posicao in range(3 + indice):
            login = get_user_model().objects.create_user(
                username=f"aluno{indice}{posicao}", password=SENHA, email=f"a{indice}{posicao}@x.com")
            aluno = Usuario.todos.create(rede=rede, unidade=unidade, user=login,
                                        nome=f"Aluno {indice}-{posicao}", status_user="Ativo")
            dados["alunos"].append(aluno)
            dados["pagamentos"].append(Pagamento.objects.create(
                rede=rede, unidade=unidade, usuario=login, plano=plano, valor_pago=Decimal("150.00"),
                data_pagamento=hoje, data_inicio=hoje, data_fim=hoje + timedelta(days=30),
                status="pago",
            ))
        # um pagamento em aberto por unidade (inadimplência)
        login = get_user_model().objects.create_user(
            username=f"pend{indice}", password=SENHA, email=f"p{indice}@x.com")
        dados["pagamentos"].append(Pagamento.objects.create(
            rede=rede, unidade=unidade, usuario=login, plano=plano, valor_pago=Decimal("150.00"),
            data_pagamento=hoje, data_inicio=hoje, data_fim=hoje + timedelta(days=30),
            status="pendente",
        ))
    return dados
