"""Reserva e cancelamento do aluno: vaga com trava, antecedencia de 2 h e prazo de 4 h.

Regras de produto cobertas:
- a reserva exige 2 h de antecedencia;
- cancelar ate 4 h antes nao deixa falta; mais perto vira falta;
- a ultima vaga nao pode ser levada duas vezes (a contagem roda com a linha travada);
- o aluno ve descricao e restricoes da atividade antes de reservar (video so depois).
"""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from agendamento.models import Agendamento
from aulas.models import Aulas
from painel.models import Painel, PainelItem
from painel_do_professor import servicos as servicos_do_professor
from painel_do_professor.models import DisponibilidadeDoProfessor
from portal_do_aluno import servicos
from portal_do_aluno.servicos import ErroDoPortal

pytestmark = pytest.mark.django_db


@pytest.fixture
def outro_aluno(db, rede, unidade):
    login = get_user_model().objects.create_user(
        username="aluno.dois", password="SenhaFortePortal!23", email="aluno.dois@x.com"
    )
    from usuarios.models import Usuario

    return Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno Dois", status_user="Ativo"
    )


@pytest.fixture
def professor(db, rede, unidade):
    from professores.models import Professor

    login = get_user_model().objects.create_user(
        username="professor.portal", password="SenhaFortePortal!23", email="prof.portal@x.com"
    )
    return Professor.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Professor Portal", status_prof="Ativo"
    )


def _turma_com_aula(rede, unidade, professor, *, categoria="forca", quando=None):
    aula = Aulas.todos.create(
        rede=rede,
        nome="Forca de pernas",
        descricao="Agachamento guiado",
        professor=professor.user,
        categorias_exercicios=categoria,
        restricao="joelho",
    )
    quando = quando or (timezone.now() + timedelta(days=2))
    turma = Painel.todos.create(
        rede=rede,
        unidade=unidade,
        nome="Atendimento individual",
        data=quando.date(),
        hora_inicio=quando.time().replace(second=0, microsecond=0),
        hora_fim=(quando + timedelta(hours=1)).time().replace(second=0, microsecond=0),
        numero_de_user=1,
        responsavel=professor.user,
    )
    PainelItem.todos.create(
        rede=rede, unidade=unidade, painel=turma, aula=aula, ordem=1
    )
    return turma


# ------------------------------------------------------------------ vaga e antecedencia
def test_ultima_vaga_nao_e_levada_duas_vezes(aluno, outro_aluno, turma, responsavel):
    turma.numero_de_user = 1
    turma.save(update_fields=["numero_de_user"])
    servicos.agendar(aluno=aluno, turma=turma)
    with pytest.raises(ErroDoPortal) as erro:
        servicos.agendar(aluno=outro_aluno, turma=turma)
    assert "cheia" in str(erro.value)
    assert Agendamento.todos.filter(painel=turma).count() == 1


def test_reserva_exige_duas_horas_de_antecedencia(aluno, rede, unidade, professor):
    quando = timezone.localtime(timezone.now()) + timedelta(minutes=45)
    turma = _turma_com_aula(rede, unidade, professor, quando=quando)
    with pytest.raises(ErroDoPortal) as erro:
        servicos.agendar(aluno=aluno, turma=turma)
    assert "2 horas" in str(erro.value)


def test_reserva_nasce_agendada_e_nao_pendente(aluno, turma):
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    assert agendamento.status == "Agendado"


def test_nao_agenda_em_turma_de_outra_rede(aluno, outra_rede, responsavel):
    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(
        rede=outra_rede, nome="Unidade Alheia", codigo="alheia", tipo="propria"
    )
    turma_alheia = Painel.objects.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        nome="Turma alheia",
        data=timezone.localdate() + timedelta(days=2),
        hora_inicio=time(19, 0),
        hora_fim=time(20, 0),
        numero_de_user=5,
        responsavel=responsavel,
    )
    with pytest.raises(ErroDoPortal) as erro:
        servicos.agendar(aluno=aluno, turma=turma_alheia)
    assert "outra academia" in str(erro.value)


# ------------------------------------------------------------------ cancelamento
def test_cancelar_com_folga_nao_deixa_falta(aluno, turma):
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    resultado = servicos.cancelar_agendamento(aluno=aluno, agendamento=agendamento)
    agendamento.refresh_from_db()
    assert agendamento.status == "Cancelado"
    assert resultado["sem_falta"] is True


def test_cancelar_em_cima_da_hora_vira_falta(aluno, rede, unidade, responsavel):
    # reserva dentro do prazo de agendar (3 h), porem ja dentro da janela de 4 h do cancelamento
    inicio = timezone.localtime(timezone.now()) + timedelta(hours=3)
    turma = Painel.objects.create(
        rede=rede,
        unidade=unidade,
        nome="Turma de hoje",
        data=inicio.date(),
        hora_inicio=inicio.time(),
        hora_fim=(inicio + timedelta(hours=1)).time(),
        numero_de_user=2,
        responsavel=responsavel,
    )
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    resultado = servicos.cancelar_agendamento(aluno=aluno, agendamento=agendamento)
    agendamento.refresh_from_db()
    assert agendamento.status == "Faltou"
    assert resultado["vira_falta"] is True


def test_aluno_nao_cancela_agendamento_alheio(aluno, outro_aluno, turma):
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    with pytest.raises(ErroDoPortal):
        servicos.cancelar_agendamento(aluno=outro_aluno, agendamento=agendamento)


# ------------------------------------------------------------------ busca de horarios
def test_busca_traz_descricao_e_restricao_da_atividade(aluno, rede, unidade, professor):
    _turma_com_aula(rede, unidade, professor)
    linhas = servicos.buscar_horarios(aluno)
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["tipos"]["codigos"] == ["forca"]
    assert "Agachamento guiado" in linha["tipos"]["descricoes"][0]
    assert linha["tipos"]["restricoes"] == ["joelho"]
    assert linha["professor"] == professor
    assert linha["ja_agendei"] is False


def test_busca_filtra_por_professor_e_tipo_de_atividade(aluno, rede, unidade, professor):
    from django.contrib.auth import get_user_model as pega_usuario

    from professores.models import Professor

    outro = pega_usuario().objects.create_user(
        username="professor.dois", password="SenhaFortePortal!23", email="prof2@x.com"
    )
    professor_dois = Professor.todos.create(
        rede=rede, unidade=unidade, user=outro, nome="Professor Dois", status_prof="Ativo"
    )
    _turma_com_aula(rede, unidade, professor, categoria="forca")
    _turma_com_aula(rede, unidade, professor_dois, categoria="cardio")

    assert len(servicos.buscar_horarios(aluno, professor=professor)) == 1
    assert len(servicos.buscar_horarios(aluno, atividade="cardio")) == 1
    assert servicos.buscar_horarios(aluno, atividade="cardio")[0]["professor"] == professor_dois
    assert len(servicos.buscar_horarios(aluno, unidade=unidade)) == 2


def test_busca_nao_vaza_horario_de_outra_rede(aluno, rede, unidade, professor, outra_rede):
    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(
        rede=outra_rede, nome="Unidade Alheia", codigo="alheia2", tipo="propria"
    )
    _turma_com_aula(rede, unidade, professor)
    from django.contrib.auth import get_user_model as pega_usuario

    from professores.models import Professor

    outro = pega_usuario().objects.create_user(username="professor.alheio", password="SenhaForte!23")
    professor_alheio = Professor.todos.create(
        rede=outra_rede, unidade=unidade_alheia, user=outro, nome="Professor Alheio", status_prof="Ativo"
    )
    _turma_com_aula(outra_rede, unidade_alheia, professor_alheio)
    assert len(servicos.buscar_horarios(aluno)) == 1


def test_tela_de_busca_abre_com_os_filtros(cliente_aluno, aluno, rede, unidade, professor):
    _turma_com_aula(rede, unidade, professor)
    resposta = cliente_aluno.get(reverse("portal:buscar_horarios"))
    assert resposta.status_code == 200
    assert len(resposta.context["horarios"]) == 1
    conteudo = resposta.content.decode()
    assert "Forca de pernas" in conteudo, conteudo[2300:5200]
    assert "Tipo de atividade" in conteudo


# ------------------------------------------------------------------ agenda do professor alimenta a busca
def test_horario_aberto_pelo_professor_aparece_na_busca_do_aluno(aluno, professor):
    """Ponta a ponta: o professor abre a agenda e o aluno encontra o horario para agendar."""
    hoje = timezone.localdate()
    disponibilidade = DisponibilidadeDoProfessor.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        professor=professor,
        nome="Avaliacao fisica",
        dia_da_semana=hoje.weekday(),
        hora_inicio=time(23, 0),
        hora_fim=time(23, 59),
        duracao_minutos=30,
        vagas_por_horario=1,
    )
    aula = Aulas.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        nome="Mobilidade",
        descricao="Alongamento guiado",
        professor=professor.user,
        categorias_exercicios="flexibilidade",
    )
    servicos_do_professor.compor_compromisso(disponibilidade, [aula])
    servicos_do_professor.materializar_disponibilidade(disponibilidade, semanas=1)

    linhas = servicos.buscar_horarios(aluno, professor=professor)
    assert linhas, "a agenda aberta pelo professor precisa aparecer para o aluno"
    assert linhas[0]["tipos"]["codigos"] == ["flexibilidade"]
