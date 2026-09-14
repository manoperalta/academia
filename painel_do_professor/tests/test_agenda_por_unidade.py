"""A agenda do professor e aberta por unidade de atendimento.

Antes de 14/09/2026 o bloco herdava sempre ``professor.unidade`` (a unidade de cadastro) e a
unicidade era por professor/dia/hora: o professor que atendia duas unidades nao conseguia
abrir a mesma janela nas duas.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from aulas.models import Aulas
from core.models import Unidade, VinculoUsuario
from core.papeis import Papel
from painel_do_professor.forms import DisponibilidadeForm
from painel_do_professor.models import DisponibilidadeDoProfessor
from professores.models import Professor


@pytest.fixture
def filial(db, rede):
    return Unidade.todos.create(rede=rede, nome="Unidade Filial", codigo="filial")


@pytest.fixture
def professor_da_agenda(db, rede, unidade):
    pessoa = get_user_model().objects.create_user(
        username="prof.agenda@exemplo.com", password="senha-de-teste-123", is_professor=True
    )
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.PROFESSOR, ativo=True
    )
    return Professor.todos.create(
        rede=rede, unidade=unidade, nome="Professor da Agenda", user=pessoa
    )


@pytest.fixture
def aula_da_rede(db, rede, unidade, professor_da_agenda):
    return Aulas.todos.create(
        rede=rede,
        unidade=unidade,
        nome="Aula da agenda",
        descricao="Descricao de teste",
        professor=professor_da_agenda.user,
        categorias_exercicios="forca",
    )


def _bloco(professor, unidade, hora="08:00"):
    return DisponibilidadeDoProfessor.todos.create(
        professor=professor,
        rede=professor.rede,
        unidade=unidade,
        nome="Atendimento",
        dia_da_semana=0,
        hora_inicio=hora,
        hora_fim="12:00",
        duracao_minutos=60,
        vagas_por_horario=1,
    )


def test_mesmo_horario_em_unidades_diferentes_e_permitido(
    db, professor_da_agenda, unidade, filial
):
    _bloco(professor_da_agenda, unidade)
    _bloco(professor_da_agenda, filial)
    assert DisponibilidadeDoProfessor.todos.filter(professor=professor_da_agenda).count() == 2


def test_mesmo_horario_na_mesma_unidade_e_recusado(db, professor_da_agenda, unidade):
    _bloco(professor_da_agenda, unidade)
    with pytest.raises(IntegrityError), transaction.atomic():
        _bloco(professor_da_agenda, unidade)


def _dados(unidade, aula):
    return {
        "unidade": unidade.pk,
        "nome": "Atendimento",
        "dia_da_semana": 0,
        "hora_inicio": "08:00",
        "hora_fim": "12:00",
        "duracao_minutos": 60,
        "vagas_por_horario": 1,
        "aulas": [aula.pk],
    }


def test_formulario_recusa_unidade_que_o_professor_nao_atende(
    db, professor_da_agenda, unidade, filial, aula_da_rede
):
    form = DisponibilidadeForm(_dados(filial, aula_da_rede), professor=professor_da_agenda)
    assert not form.is_valid()
    assert "unidade" in form.errors


def test_formulario_aceita_a_unidade_de_atendimento(
    db, professor_da_agenda, unidade, aula_da_rede
):
    form = DisponibilidadeForm(_dados(unidade, aula_da_rede), professor=professor_da_agenda)
    assert form.is_valid(), form.errors
    bloco = form.save(commit=False)
    assert bloco.unidade == unidade
