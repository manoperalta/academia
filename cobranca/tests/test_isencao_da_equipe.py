"""Equipe vinculada ao tenant nao paga: professor (e demais papeis) ficam fora da cobranca.

Requisito de produto: "professores sao isentos de pagamento pois estarao vinculados a tenant
(admin da rede e ou gestor da unidade)". Isento significa: nao gera cobranca, nao entra na regua
e nao aparece na inadimplencia -- nem no numero do painel.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from cobranca.models import AutorizacaoDeDebito, CobrancaRecorrente
from cobranca import servicos
from core.models import VinculoUsuario
from core.papeis import Papel
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db


def _autorizar(usuario, rede, _unidade=None):
    return AutorizacaoDeDebito.objects.create(
        rede=rede, aluno=usuario, situacao=AutorizacaoDeDebito.Situacao.ATIVA
    )


def _entrar_na_equipe(usuario, rede, papel):
    return VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=papel, ativo=True)


@pytest.fixture
def professor_vinculado(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="professor.isento", password="SenhaForte!23", email="prof.isento@x.com"
    )
    perfil = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Professor Isento", status_user="Ativo"
    )
    VinculoUsuario.todos.create(usuario=login, rede=rede, papel=Papel.PROFESSOR, ativo=True)
    _autorizar(perfil, rede, unidade)
    return perfil


@pytest.fixture
def gestor_vinculado(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="gestor.isento", password="SenhaForte!23", email="gestor@x.com"
    )
    perfil = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Gestor Isento", status_user="Ativo"
    )
    VinculoUsuario.todos.create(usuario=login, rede=rede, papel=Papel.GESTOR_UNIDADE, ativo=True)
    _autorizar(perfil, rede, unidade)
    return perfil


def test_professor_nao_gera_cobranca(rede, unidade, aluno, professor_vinculado):
    _autorizar(aluno, rede, unidade)
    resultado = servicos.gerar_cobrancas_do_mes(rede, timezone.localdate(), dry_run=True)
    nomes = [linha["aluno"] for linha in resultado["criadas"]]
    assert "Aluno Cobranca" in nomes
    assert "Professor Isento" not in nomes
    assert "Professor Isento" in resultado["isentos"]


def test_equipe_nao_gera_cobranca_de_verdade(rede, unidade, aluno, professor_vinculado, gestor_vinculado):
    _autorizar(aluno, rede, unidade)
    servicos.gerar_cobrancas_do_mes(rede, timezone.localdate())
    cobrados = set(
        CobrancaRecorrente.objects.filter(rede=rede).values_list("aluno__nome", flat=True)
    )
    assert cobrados == {"Aluno Cobranca"}


def test_professor_nao_aparece_na_inadimplencia(rede, unidade, aluno, professor_vinculado):
    competencia = timezone.localdate().replace(day=1) - timedelta(days=32)
    for perfil, valor in ((aluno, Decimal("199.00")), (professor_vinculado, Decimal("199.00"))):
        CobrancaRecorrente.objects.create(
            rede=rede,
            unidade=unidade,
            aluno=perfil,
            competencia=competencia,
            valor=valor,
            vencimento=competencia + timedelta(days=9),
        )
    nomes = [linha["cobranca"].aluno.nome for linha in servicos.lista_de_inadimplentes(rede)]
    assert nomes == ["Aluno Cobranca"]
    assert servicos.resumo_da_inadimplencia(rede)["quantidade_vencidas"] == 1


def test_aluno_que_tambem_e_da_equipe_de_outra_rede_continua_pagando_a_dele(
    rede, outra_rede, unidade, aluno
):
    """A isencao e do vinculo: quem e da equipe de OUTRA rede aqui segue como aluno pagante."""
    _entrar_na_equipe(aluno.user, outra_rede, Papel.PROFESSOR)
    _autorizar(aluno, rede, unidade)
    assert aluno.user.pk in servicos.usuarios_isentos(outra_rede)
    assert aluno.user.pk not in servicos.usuarios_isentos(rede)
    resultado = servicos.gerar_cobrancas_do_mes(rede, timezone.localdate(), dry_run=True)
    assert "Aluno Cobranca" in [linha["aluno"] for linha in resultado["criadas"]]


def test_vinculo_inativo_nao_isenta(rede, unidade, aluno):
    _entrar_na_equipe(aluno.user, rede, Papel.RECEPCAO)
    VinculoUsuario.todos.filter(usuario=aluno.user).update(ativo=False)
    assert servicos.usuarios_isentos(rede) == set()
