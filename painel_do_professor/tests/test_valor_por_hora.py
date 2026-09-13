"""Valor por hora: definido no painel, apurado pelas horas e visivel para o professor."""

from __future__ import annotations

from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamento.models import Agendamento
from painel.models import Painel
from painel_do_professor import servicos
from remuneracao.models import RegraDeComissao, TipoDeComissao
from remuneracao.servicos import (
    ErroDeRemuneracao,
    aulas_dadas,
    calcular_apuracao,
    horas_trabalhadas,
)

pytestmark = pytest.mark.django_db


def _turma(professor, *, dia=None, inicio=time(19, 0), fim=time(20, 0), nome="Atendimento"):
    return Painel.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        responsavel=professor.user,
        nome=nome,
        data=dia or timezone.localdate(),
        hora_inicio=inicio,
        hora_fim=fim,
        numero_de_user=1,
    )


def _agendar(professor, aluno, turma, status="Concluido"):
    return Agendamento.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        painel=turma,
        aluno=aluno.user,
        status=status,
    )


# ------------------------------------------------------------------ valor da hora
def test_valor_por_hora_e_regra_por_hora_e_nao_sobrescreve_o_historico(professor):
    professor.definir_valor_por_hora(Decimal("40.00"))
    professor.definir_valor_por_hora(Decimal("55.00"))
    regras = RegraDeComissao.objects.filter(professor=professor, tipo=TipoDeComissao.POR_HORA)
    assert regras.count() == 2
    assert regras.filter(ativo=True).count() == 1
    antiga = regras.order_by("criado_em").first()
    assert antiga.ativo is False
    assert antiga.fim_vigencia == timezone.localdate() - timedelta(days=1)
    assert professor.valor_por_hora == Decimal("55.00")


def test_sem_valor_definido_o_financeiro_diz_o_que_falta(professor):
    assert professor.valor_por_hora is None
    with pytest.raises(ErroDeRemuneracao) as erro:
        calcular_apuracao(professor, professor.unidade, *_mes())
    assert "regra" in str(erro.value)


def test_valor_da_hora_vira_comissao_pelas_horas_trabalhadas(professor, aluno):
    professor.definir_valor_por_hora(Decimal("50.00"))
    turma = _turma(professor, inicio=time(19, 0), fim=time(20, 0))
    _agendar(professor, aluno, turma)
    calculo = calcular_apuracao(professor, professor.unidade, *_mes())
    assert calculo["base_de_calculo"] == Decimal("1.00")
    assert calculo["total"] == Decimal("50.00")
    assert calculo["linhas"][0]["tipo"] == "por_hora"


def test_duas_turmas_de_noventa_minutos_somam_tres_horas(professor, aluno, outro_aluno):
    professor.definir_valor_por_hora(Decimal("40.00"))
    primeira = _turma(professor, inicio=time(8, 0), fim=time(9, 30))
    segunda = _turma(professor, inicio=time(10, 0), fim=time(11, 30))
    _agendar(professor, aluno, primeira)
    _agendar(professor, outro_aluno, segunda)
    calculo = calcular_apuracao(professor, professor.unidade, *_mes())
    assert calculo["base_de_calculo"] == Decimal("3.00")
    assert calculo["total"] == Decimal("120.00")


def test_atendimento_cancelado_ou_falta_nao_paga_hora(professor, aluno, outro_aluno):
    professor.definir_valor_por_hora(Decimal("50.00"))
    cancelada = _turma(professor, inicio=time(8, 0), fim=time(9, 0))
    faltou = _turma(professor, inicio=time(10, 0), fim=time(11, 0))
    _agendar(professor, aluno, cancelada, status="Cancelado")
    _agendar(professor, outro_aluno, faltou, status="Faltou")
    horas, _ = horas_trabalhadas(professor, professor.unidade, *_mes())
    assert horas == Decimal("0.00")


def test_dois_alunos_no_mesmo_horario_contam_uma_hora_so(professor, aluno, outro_aluno):
    professor.definir_valor_por_hora(Decimal("50.00"))
    turma = _turma(professor, inicio=time(19, 0), fim=time(20, 0))
    _agendar(professor, aluno, turma)
    _agendar(professor, outro_aluno, turma)
    horas, fonte = horas_trabalhadas(professor, professor.unidade, *_mes())
    assert horas == Decimal("1.00")
    assert "1 turma" in fonte


def test_horas_de_outro_professor_nao_entram(professor, outro_professor, aluno):
    professor.definir_valor_por_hora(Decimal("50.00"))
    turma_do_outro = _turma(outro_professor, inicio=time(19, 0), fim=time(21, 0))
    _agendar(outro_professor, aluno, turma_do_outro)
    calculo = calcular_apuracao(professor, professor.unidade, *_mes())
    assert calculo["base_de_calculo"] == Decimal("0.00")
    assert calculo["total"] == Decimal("0.00")


def test_aulas_dadas_usa_o_responsavel_da_turma(professor, aluno):
    """Regressao: antes a contagem procurava ``painel.professor`` (campo que nao existe) e dava zero."""
    turma = _turma(professor)
    _agendar(professor, aluno, turma)
    quantidade, fonte = aulas_dadas(professor, professor.unidade, *_mes())
    assert quantidade == 1
    assert "agenda" in fonte


# ------------------------------------------------------------------ tela do professor
def test_financeiro_do_professor_mostra_valor_hora_horas_e_previsao(professor, aluno):
    professor.definir_valor_por_hora(Decimal("60.00"))
    _agendar(professor, aluno, _turma(professor, inicio=time(19, 0), fim=time(20, 30)))
    financeiro = servicos.meu_financeiro(professor)
    assert financeiro["valor_por_hora"] == Decimal("60.00")
    assert financeiro["horas_no_mes"] == Decimal("1.50")
    assert financeiro["previsao"] == Decimal("90.00")
    assert financeiro["pendencia"] == ""


def test_financeiro_avisa_quando_nao_ha_valor_definido(professor):
    financeiro = servicos.meu_financeiro(professor)
    assert financeiro["valor_por_hora"] is None
    assert "regra" in financeiro["pendencia"]


def test_professor_abre_a_tela_de_comissoes_com_o_valor_da_hora(cliente_professor, professor):
    professor.definir_valor_por_hora(Decimal("70.00"))
    resposta = cliente_professor.get(reverse("professor:comissoes"))
    assert resposta.status_code == 200
    assert resposta.context["financeiro"]["valor_por_hora"] == Decimal("70.00")


def _mes():
    from remuneracao.servicos import competencia

    return competencia(timezone.localdate())
