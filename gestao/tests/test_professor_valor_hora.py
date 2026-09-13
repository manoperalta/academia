"""O valor por hora do professor e definido no painel do admin da rede / gestor da unidade."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from professores.models import Professor
from remuneracao.models import RegraDeComissao, TipoDeComissao

pytestmark = pytest.mark.django_db


def _payload(**extra):
    dados = {
        "nome": "Professor do Painel",
        "email_prof": "professor.painel@exemplo.com",
        "status_prof": "Ativo",
        "criar_login": "on",
    }
    dados.update(extra)
    return dados


def test_admin_da_rede_define_o_valor_por_hora(cliente_logado, rede):
    resposta = cliente_logado.post(
        reverse("gestao:professor_novo"), _payload(valor_por_hora="80.00")
    )
    assert resposta.status_code == 302
    professor = Professor.todos.get(nome="Professor do Painel")
    assert professor.valor_por_hora == Decimal("80.00")
    regra = RegraDeComissao.objects.get(professor=professor, tipo=TipoDeComissao.POR_HORA)
    assert regra.valor == Decimal("80.00")
    assert regra.ativo is True


def test_gestor_da_unidade_define_e_o_historico_fica(cliente_logado, rede):
    cliente_logado.post(reverse("gestao:professor_novo"), _payload(valor_por_hora="50.00"))
    professor = Professor.todos.get(nome="Professor do Painel")

    resposta = cliente_logado.post(
        reverse("gestao:professor_editar", args=[professor.pk]),
        _payload(valor_por_hora="65.00"),
    )
    assert resposta.status_code == 302
    professor.refresh_from_db()
    assert professor.valor_por_hora == Decimal("65.00")
    regras = RegraDeComissao.objects.filter(professor=professor, tipo=TipoDeComissao.POR_HORA)
    assert regras.count() == 2
    assert regras.filter(ativo=True).count() == 1


def test_cadastro_sem_valor_por_hora_continua_valendo(cliente_logado, rede):
    resposta = cliente_logado.post(reverse("gestao:professor_novo"), _payload())
    assert resposta.status_code == 302
    professor = Professor.todos.get(nome="Professor do Painel")
    assert professor.valor_por_hora is None
    assert RegraDeComissao.objects.filter(professor=professor).count() == 0


def test_recepcao_nao_define_valor_por_hora(cliente_recepcao, rede):
    resposta = cliente_recepcao.post(
        reverse("gestao:professor_novo"), _payload(valor_por_hora="999.00")
    )
    assert resposta.status_code == 403
    assert not Professor.todos.filter(nome="Professor do Painel").exists()
    assert not RegraDeComissao.objects.filter(valor=Decimal("999.00")).exists()


def test_professor_nao_define_o_proprio_valor(cliente_professor, rede):
    resposta = cliente_professor.post(
        reverse("gestao:professor_novo"), _payload(valor_por_hora="999.00")
    )
    assert resposta.status_code == 403
    assert not RegraDeComissao.objects.filter(valor=Decimal("999.00")).exists()
