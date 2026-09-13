"""Testes do painel do professor: agenda, chamada, treinos, alunos e comissoes."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from agendamento.models import Agendamento
from painel_do_professor import servicos
from painel_do_professor.models import OcorrenciaDaTurma, SubstituicaoDeTurma
from treinos.models import Treino
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ agenda e chamada


def test_agenda_mostra_as_minhas_turmas(cliente_professor, turma, agendamento):
    resposta = cliente_professor.get(reverse("professor:agenda"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Turma das 7h" in corpo
    assert "1/12" in corpo or "1 de 12" in corpo or "vaga" in corpo


def test_agenda_de_outro_dia_nao_traz_a_turma(cliente_professor, turma):
    ontem = (timezone.localdate() - timedelta(days=1)).isoformat()
    resposta = cliente_professor.get(reverse("professor:agenda"), {"dia": ontem})
    assert resposta.status_code == 200
    assert "Turma das 7h" not in resposta.content.decode()


def test_chamada_marca_presenca_e_falta(cliente_professor, turma, agendamento):
    outro = Agendamento.objects.create(
        rede=turma.rede,
        unidade=turma.unidade,
        painel=turma,
        aluno=turma.responsavel,
        data_agendamento=timezone.now(),
        status="pendente",
    )
    resposta = cliente_professor.post(
        reverse("professor:chamada", args=[turma.pk]),
        {
            f"aluno_{agendamento.pk}": "presente",
            f"aluno_{outro.pk}": "falta",
        },
    )
    assert resposta.status_code == 302
    agendamento.refresh_from_db()
    outro.refresh_from_db()
    assert agendamento.status == "presente" and outro.status == "falta"


def test_professor_nao_abre_turma_de_outro(cliente_professor, outra_rede, professor):
    from datetime import time

    from painel.models import Painel

    alheia = Painel.objects.create(
        rede=outra_rede,
        nome="Turma alheia",
        data=timezone.localdate(),
        hora_inicio=time(9, 0),
        hora_fim=time(10, 0),
        responsavel=professor.user,
        numero_de_user=5,
    )
    assert cliente_professor.get(reverse("professor:turma", args=[alheia.pk])).status_code == 404


# ------------------------------------------------------------------ ocorrencias e substituicao


def test_ocorrencia_exige_descricao_e_registra(cliente_professor, turma, aluno):
    vazio = cliente_professor.post(
        reverse("professor:ocorrencia", args=[turma.pk]),
        {"aluno": aluno.pk, "tipo": "dor_ou_lesao", "descricao": "  "},
    )
    assert vazio.status_code == 302
    assert OcorrenciaDaTurma.objects.count() == 0

    cliente_professor.post(
        reverse("professor:ocorrencia", args=[turma.pk]),
        {
            "aluno": aluno.pk,
            "tipo": "dor_ou_lesao",
            "descricao": "Sentiu dor no joelho no agachamento",
        },
    )
    ocorrencia = OcorrenciaDaTurma.objects.get()
    assert ocorrencia.aluno == aluno and ocorrencia.tipo == "dor_ou_lesao"
    assert "joelho" in ocorrencia.descricao
    assert (
        "joelho"
        in cliente_professor.get(reverse("professor:turma", args=[turma.pk])).content.decode()
    )


def test_substituicao_troca_o_responsavel(cliente_professor, turma, outro_professor):
    resposta = cliente_professor.post(
        reverse("professor:substituicao", args=[turma.pk]),
        {"substituto": outro_professor.pk, "motivo": "atestado"},
    )
    assert resposta.status_code == 302
    turma.refresh_from_db()
    assert turma.responsavel_id == outro_professor.user_id
    assert SubstituicaoDeTurma.objects.filter(turma=turma, substituto=outro_professor).exists()


def test_substituicao_recusa_o_mesmo_professor(turma, professor):
    with pytest.raises(servicos.ErroDoProfessor):
        servicos.registrar_substituicao(turma=turma, substituto=professor)


# ------------------------------------------------------------------ treinos


def test_prescrever_treino_pela_tela(cliente_professor, aluno):
    resposta = cliente_professor.post(
        reverse("professor:prescrever"),
        {"aluno": aluno.pk, "nome": "Hipertrofia A", "objetivo": "hipertrofia"},
    )
    assert resposta.status_code == 302
    treino = Treino.objects.get()
    assert treino.professor.nome == "Professor Treino" and treino.aluno == aluno


def test_incluir_exercicio_pela_tela(cliente_professor, aluno, professor):
    treino = Treino.objects.create(
        rede=aluno.rede,
        aluno=aluno,
        professor=professor,
        nome="Treino",
        situacao=Treino.Situacao.ATIVO,
    )
    resposta = cliente_professor.post(
        reverse("professor:adicionar_exercicio", args=[treino.pk]),
        {"nome": "Supino reto", "series": 4, "repeticoes": "10", "carga_sugerida": "40"},
    )
    assert resposta.status_code == 302
    exercicio = treino.exercicios.get()
    assert exercicio.nome == "Supino reto" and exercicio.series == 4


def test_duplicar_treino_pela_tela(cliente_professor, aluno, outro_aluno, professor):
    treino = Treino.objects.create(
        rede=aluno.rede,
        aluno=aluno,
        professor=professor,
        nome="Base",
        situacao=Treino.Situacao.ATIVO,
    )
    resposta = cliente_professor.post(
        reverse("professor:duplicar_treino", args=[treino.pk]), {"aluno": outro_aluno.pk}
    )
    assert resposta.status_code == 302
    copia = Treino.objects.get(aluno=outro_aluno)
    assert copia.nome.endswith("(copia)") and copia.situacao == Treino.Situacao.RASCUNHO


# ------------------------------------------------------------------ alunos e avaliacoes


def test_meus_alunos_so_traz_quem_esta_nas_minhas_turmas(
    cliente_professor, turma, agendamento, outro_aluno
):
    resposta = cliente_professor.get(reverse("professor:alunos"))
    corpo = resposta.content.decode()
    assert "Aluno Treino" in corpo
    assert "Outro Aluno" not in corpo


def test_ficha_do_aluno_mostra_saude_frequencia_e_evolucao(
    cliente_professor, turma, agendamento, aluno, ficha
):
    from treinos import servicos as servicos_de_treino

    hoje = timezone.localdate()
    servicos_de_treino.registrar_avaliacao(
        aluno=aluno,
        peso=Decimal("85.00"),
        altura=Decimal("1.75"),
        percentual_de_gordura=Decimal("25"),
        data=hoje - timedelta(days=30),
    )
    servicos_de_treino.registrar_avaliacao(
        aluno=aluno,
        peso=Decimal("80.00"),
        altura=Decimal("1.75"),
        percentual_de_gordura=Decimal("20"),
        data=hoje,
    )
    resposta = cliente_professor.get(reverse("professor:aluno", args=[aluno.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "coluna" in corpo, "a ficha de saude do aluno nao apareceu na pagina"
    assert "Evolução" in corpo, "a secao de evolucao nao apareceu"
    assert "-5" in corpo, "a diferenca de peso entre as avaliacoes nao apareceu"


def test_avaliacao_pela_tela_e_listagem(cliente_professor, turma, agendamento, aluno):
    resposta = cliente_professor.post(
        reverse("professor:registrar_avaliacao"),
        {
            "aluno": aluno.pk,
            "peso": "80",
            "altura": "1.75",
            "percentual_de_gordura": "18",
            "cintura": "88",
        },
    )
    assert resposta.status_code == 302
    pagina = cliente_professor.get(reverse("professor:avaliacoes"))
    assert pagina.status_code == 200
    assert "80" in pagina.content.decode()


def test_aluno_de_outra_rede_nao_aparece_na_ficha(cliente_professor, outra_rede):
    from django.contrib.auth import get_user_model

    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    login = get_user_model().objects.create_user(username="alheio.prof", password="SenhaAlheia!23")
    alheio = Usuario.todos.create(
        rede=outra_rede, unidade=unidade_alheia, user=login, nome="Alheio", status_user="Ativo"
    )
    assert cliente_professor.get(reverse("professor:aluno", args=[alheio.pk])).status_code == 404


def test_comissoes_do_professor(cliente_professor, professor, rede, unidade):
    from remuneracao.models import ApuracaoDeComissao

    hoje = timezone.localdate()
    ApuracaoDeComissao.objects.create(
        rede=rede,
        unidade=unidade,
        professor=professor,
        inicio=hoje.replace(day=1),
        fim=hoje,
        valor_devido=Decimal("500.00"),
    )
    resposta = cliente_professor.get(reverse("professor:comissoes"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "500,00" in corpo or "500.00" in corpo


def test_quem_nao_e_professor_recebe_403(cliente_aluno):
    assert cliente_aluno.get(reverse("professor:agenda")).status_code == 403


def test_visitante_vai_para_o_login(client):
    resposta = client.get(reverse("professor:agenda"))
    assert resposta.status_code in (302, 403)
