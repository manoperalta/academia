"""Meu plano: pacote, limites, avisos e faturas do tenant."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from plataforma.models import Assinatura, Pacote
from plataforma.servicos import gerar_fatura
from usuarios.models import Usuario


@pytest.fixture
def pacote(db):
    return Pacote.objects.create(
        nome="Prata",
        codigo="prata",
        limite_alunos=100,
        limite_professores=5,
        preco_mensal="150.00",
    )


@pytest.fixture
def assinatura_do_tenant(db, rede, pacote):
    hoje = timezone.localdate()
    return Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo="mensal",
        inicio=hoje,
        renovacao_em=hoje + timedelta(days=30),
    )


def test_meu_plano_mostra_pacote_limites_e_faturas(cliente_logado, rede, assinatura_do_tenant):
    gerar_fatura(assinatura_do_tenant)
    resposta = cliente_logado.get(reverse("gestao:plano"))
    assert resposta.status_code == 200
    assert resposta.context["situacao"]["limites"]["alunos"] == 100
    conteudo = resposta.content.decode()
    assert "Prata" in conteudo
    assert "FAT-" in conteudo


def test_meu_plano_sem_assinatura(cliente_logado, rede):
    resposta = cliente_logado.get(reverse("gestao:plano"))
    assert resposta.status_code == 200
    assert "Sem assinatura" in resposta.content.decode()


def test_recepcao_nao_acessa_meu_plano(cliente_recepcao):
    assert cliente_recepcao.get(reverse("gestao:plano")).status_code == 403


def test_aviso_de_limite_aparece_no_painel(cliente_logado, rede, assinatura_do_tenant):
    for indice in range(85):
        Usuario.todos.create(
            rede=rede,
            nome=f"Aluno {indice}",
            email_user=f"aluno{indice}@exemplo.com",
            telefone_user="51999999999",
            status_user="Ativo",
        )
    resposta = cliente_logado.get(reverse("gestao:visao_geral"))
    assert "85%" in resposta.content.decode()
