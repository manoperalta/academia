"""Agenda do professor: abrir horario, compor o compromisso com aulas e materializar as turmas."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from aulas.models import Aulas
from midia.models import ArquivoDeMidia
from painel.models import Painel
from painel_do_professor import servicos
from painel_do_professor.models import DisponibilidadeDoProfessor, TurmaMaterializada
from agendamento.models import Agendamento

pytestmark = pytest.mark.django_db


@pytest.fixture
def aula(db, rede, professor):
    return Aulas.todos.create(
        rede=rede,
        nome="Mobilidade de quadril",
        descricao="Sequencia de mobilidade com respiracao",
        professor=professor.user,
        categorias_exercicios="flexibilidade",
    )


@pytest.fixture
def outra_aula(db, rede, professor):
    return Aulas.todos.create(
        rede=rede,
        nome="Forca de pernas",
        descricao="Agachamento e afundo guiados",
        professor=professor.user,
        categorias_exercicios="forca",
    )


def _bloco(professor, *, dia=None, inicio=time(19, 0), fim=time(21, 0), duracao=60, aulas=()):
    hoje = timezone.localdate()
    disponibilidade = DisponibilidadeDoProfessor.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        professor=professor,
        nome="Atendimento individual",
        dia_da_semana=hoje.weekday() if dia is None else dia,
        hora_inicio=inicio,
        hora_fim=fim,
        duracao_minutos=duracao,
        vagas_por_horario=1,
    )
    if aulas:
        servicos.compor_compromisso(disponibilidade, list(aulas))
    return disponibilidade


# ------------------------------------------------------------------ fatiamento
def test_janela_vira_horarios_do_tamanho_do_compromisso(professor):
    bloco = _bloco(professor, inicio=time(19, 0), fim=time(21, 0), duracao=60)
    horarios = bloco.horarios()
    assert horarios == [(time(19, 0), time(20, 0)), (time(20, 0), time(21, 0))]
    assert bloco.sobra_minutos == 0


def test_sobra_de_tempo_e_informada_e_nao_vira_horario(professor):
    bloco = _bloco(professor, inicio=time(19, 0), fim=time(21, 0), duracao=45)
    assert len(bloco.horarios()) == 2
    assert bloco.sobra_minutos == 30


def test_tempo_maior_que_a_janela_e_recusado(professor):
    from django.core.exceptions import ValidationError

    bloco = _bloco(professor, inicio=time(19, 0), fim=time(20, 0), duracao=90)
    with pytest.raises(ValidationError):
        bloco.full_clean()


# ------------------------------------------------------------------ materializacao
def test_materializa_as_proximas_semanas_no_dia_certo(professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    resultado = servicos.materializar_disponibilidade(bloco, semanas=4)
    assert resultado["criadas"] == 8  # 4 semanas x 2 horarios
    hoje = timezone.localdate()
    turmas = Painel.todos.filter(responsavel=professor.user).order_by("data", "hora_inicio")
    assert turmas.count() == 8
    assert all(turma.data.weekday() == hoje.weekday() for turma in turmas)
    assert turmas.first().numero_de_user == 1
    assert turmas.first().itens.count() == 1


def test_materializacao_e_idempotente(professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=2)
    antes = Painel.todos.count()
    resultado = servicos.materializar_disponibilidade(bloco, semanas=2)
    assert resultado["criadas"] == 0
    assert Painel.todos.count() == antes
    assert TurmaMaterializada.objects.filter(disponibilidade=bloco).count() == antes


def test_dry_run_nao_grava(professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    resultado = servicos.materializar_disponibilidade(bloco, semanas=2, dry_run=True)
    assert resultado["criadas"] == 4
    assert Painel.todos.count() == 0


def test_aulas_viram_itens_na_ordem(professor, aula, outra_aula):
    bloco = _bloco(professor, aulas=[outra_aula, aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    turma = Painel.todos.order_by("hora_inicio").first()
    assert [item.aula_id for item in turma.itens.order_by("ordem")] == [outra_aula.pk, aula.pk]
    assert [item.ordem for item in turma.itens.order_by("ordem")] == [1, 2]


def test_trocar_as_aulas_reflete_sem_duplicar(professor, aula, outra_aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    servicos.compor_compromisso(bloco, [aula, outra_aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    turma = Painel.todos.order_by("hora_inicio").first()
    assert turma.itens.count() == 2


def test_horario_com_aluno_agendado_nunca_e_apagado(professor, aluno, aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    turma = Painel.todos.order_by("data", "hora_inicio").first()
    Agendamento.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        painel=turma,
        aluno=aluno.user,
        status="Agendado",
    )
    # o professor muda a janela: o horario das 19h deixa de existir
    bloco.hora_inicio = time(20, 0)
    bloco.hora_fim = time(21, 0)
    bloco.save(update_fields=["hora_inicio", "hora_fim"])
    resultado = servicos.materializar_disponibilidade(bloco, semanas=1)
    turma.refresh_from_db()
    assert turma.arquivado_em is None, "turma com aluno agendado nao pode ser retirada"
    assert resultado["preservadas"] >= 1
    assert any("agendado" in aviso for aviso in resultado["avisos"])


def test_horario_sem_agendamento_sai_quando_a_agenda_muda(professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    antiga = Painel.todos.order_by("data", "hora_inicio").first()
    bloco.hora_inicio = time(20, 0)
    bloco.hora_fim = time(21, 0)
    bloco.save(update_fields=["hora_inicio", "hora_fim"])
    resultado = servicos.materializar_disponibilidade(bloco, semanas=1)
    antiga.refresh_from_db()
    assert resultado["arquivadas"] >= 1
    assert antiga.arquivado_em is not None


def test_encerrar_bloco_preserva_o_que_tem_aluno(professor, aluno, aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    com_aluno = Painel.todos.order_by("data", "hora_inicio").first()
    Agendamento.todos.create(
        rede=professor.rede,
        unidade=professor.unidade,
        painel=com_aluno,
        aluno=aluno.user,
        status="Agendado",
    )
    resultado = servicos.encerrar_disponibilidade(bloco)
    bloco.refresh_from_db()
    com_aluno.refresh_from_db()
    assert bloco.ativo is False
    assert com_aluno.arquivado_em is None
    assert resultado["arquivadas"] == 1


def test_vigencia_limita_a_materializacao(professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    bloco.fim_vigencia = timezone.localdate() + timedelta(days=7)
    bloco.save(update_fields=["fim_vigencia"])
    servicos.materializar_disponibilidade(bloco, semanas=4)
    assert Painel.todos.count() == 4  # 2 semanas x 2 horarios


def test_agenda_de_um_professor_nao_toca_a_de_outro(professor, outro_professor, aula):
    bloco = _bloco(professor, aulas=[aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    servicos.materializar_agenda(outro_professor)
    assert Painel.todos.filter(responsavel=outro_professor.user).count() == 0


# ------------------------------------------------------------------ tipo de atividade
def test_tipo_de_atividade_vem_das_aulas_do_compromisso(professor, aula, outra_aula):
    bloco = _bloco(professor, aulas=[aula, outra_aula])
    servicos.materializar_disponibilidade(bloco, semanas=1)
    turma = Painel.todos.first()
    tipos = servicos.tipos_de_atividade(turma)
    assert tipos["categorias"] == ["Flexibilidade/Alongamento", "Treinamento de Força"]
    assert tipos["total_de_aulas"] == 2


def test_aviso_quando_os_videos_nao_fecham_o_tempo(professor, aula):
    ArquivoDeMidia.objects.create(
        rede=professor.rede,
        aula=aula,
        titulo="Mobilidade",
        tipo="video",
        situacao=ArquivoDeMidia.Situacao.PRONTO,
        duracao_segundos=20 * 60,
    )
    bloco = _bloco(professor, aulas=[aula], duracao=60)
    assert aula.duracao_em_minutos == 20
    assert "20 min" in servicos.aviso_de_composicao(bloco)
    bloco.duracao_minutos = 15
    assert servicos.aviso_de_composicao(bloco) == ""


# ------------------------------------------------------------------ telas
def test_professor_abre_horario_pela_tela(cliente_professor, aula):
    resposta = cliente_professor.get(reverse("professor:disponibilidades"))
    assert resposta.status_code == 200
    hoje = timezone.localdate()
    resposta = cliente_professor.post(
        reverse("professor:abrir_agenda"),
        {
            "nome": "Atendimento individual",
            "dia_da_semana": hoje.weekday(),
            "hora_inicio": "19:00",
            "hora_fim": "21:00",
            "duracao_minutos": 60,
            "vagas_por_horario": 1,
            "aulas": [aula.pk],
        },
    )
    assert resposta.status_code == 302
    bloco = DisponibilidadeDoProfessor.todos.get()
    assert bloco.composicao.count() == 1
    assert Painel.todos.filter(responsavel=bloco.professor.user).count() >= 2


def test_abrir_horario_sem_aula_e_recusado(cliente_professor):
    hoje = timezone.localdate()
    resposta = cliente_professor.post(
        reverse("professor:abrir_agenda"),
        {
            "nome": "Atendimento",
            "dia_da_semana": hoje.weekday(),
            "hora_inicio": "19:00",
            "hora_fim": "20:00",
            "duracao_minutos": 60,
            "vagas_por_horario": 1,
            "aulas": [],
        },
    )
    assert resposta.status_code == 200
    assert not DisponibilidadeDoProfessor.todos.exists()


def test_aluno_nao_abre_agenda_de_professor(cliente_aluno):
    resposta = cliente_aluno.get(reverse("professor:disponibilidades"))
    assert resposta.status_code == 403


def test_professor_nao_edita_agenda_de_outro(cliente_professor, outro_professor, aula):
    bloco_do_outro = _bloco(outro_professor, aulas=[aula])
    resposta = cliente_professor.get(
        reverse("professor:editar_disponibilidade", args=[bloco_do_outro.pk])
    )
    assert resposta.status_code == 404
