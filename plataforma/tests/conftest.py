"""Fixtures da plataforma (Fase 3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from plataforma.models import Assinatura, ModuloPacote, Pacote


def criar_pacote(codigo, nome, alunos, professores, unidades, preco, modulos):
    return Pacote.objects.create(
        nome=nome,
        codigo=codigo,
        limite_alunos=alunos,
        limite_professores=professores,
        limite_unidades=unidades,
        preco_mensal=preco,
        preco_anual=str(float(preco) * 12),
        modulos=modulos,
    )


def criar_assinatura(rede, pacote, ciclo="mensal", dias=30, trial=False):
    hoje = timezone.localdate()
    return Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo=ciclo,
        inicio=hoje,
        renovacao_em=hoje + timedelta(days=dias),
        trial_termina_em=(hoje + timedelta(days=dias)) if trial else None,
    )


def criar_alunos(rede, quantidade, status="Ativo"):
    from usuarios.models import Usuario

    return [
        Usuario.todos.create(
            rede=rede,
            nome=f"Aluno {indice}",
            email_user=f"aluno{indice}@exemplo.com",
            telefone_user="51999999999",
            status_user=status,
        )
        for indice in range(quantidade)
    ]


@pytest.fixture
def pacote_prata(db):
    return criar_pacote("prata", "Prata", 100, 5, 1, "150.00", [ModuloPacote.IMPRESSAO_PDF])


@pytest.fixture
def pacote_bronze(db):
    return criar_pacote(
        "bronze",
        "Bronze",
        150,
        10,
        1,
        "250.00",
        [ModuloPacote.WHATSAPP, ModuloPacote.RELATORIOS_AVANCADOS],
    )


@pytest.fixture
def pacote_ouro(db):
    return criar_pacote(
        "ouro", "Ouro", None, None, None, "500.00", [modulo.value for modulo in ModuloPacote]
    )


@pytest.fixture
def assinatura(db, rede, pacote_prata):
    return criar_assinatura(rede, pacote_prata)


@pytest.fixture
def suporte(db):
    return get_user_model().objects.create_user(
        username="suporte.teste",
        password="SenhaSuporte123",
        is_staff=True,
        email="suporte@safestack.com.br",
    )


@pytest.fixture
def cliente_plataforma(db, suporte):
    cliente = Client()
    cliente.force_login(suporte)
    return cliente
