"""Testes de prescricao, execucao e avaliacao fisica."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from treinos import servicos
from treinos.models import Treino
from treinos.servicos import ErroDeTreino

pytestmark = pytest.mark.django_db


def test_prescrever_treino_com_exercicios_na_ordem(rede, aluno, professor):
    treino = servicos.prescrever_treino(
        aluno=aluno,
        professor=professor,
        nome="Full body",
        objetivo="hipertrofia",
        exercicios=[
            {"nome": "Supino", "series": 4, "repeticoes": "10"},
            {"nome": "Remada", "series": 4, "repeticoes": "12"},
        ],
    )
    assert treino.situacao == Treino.Situacao.ATIVO
    assert treino.total_de_exercicios == 2
    assert [item.nome for item in treino.exercicios.all()] == ["Supino", "Remada"]


def test_prescrever_exige_nome_e_objetivo_valido(aluno):
    with pytest.raises(ErroDeTreino):
        servicos.prescrever_treino(aluno=aluno, nome="  ")
    with pytest.raises(ErroDeTreino):
        servicos.prescrever_treino(aluno=aluno, nome="Treino", objetivo="inventado")


def test_periodo_invertido_e_recusado(aluno):
    hoje = timezone.localdate()
    with pytest.raises(ErroDeTreino):
        servicos.prescrever_treino(
            aluno=aluno, nome="Treino", inicio=hoje, fim=hoje - timedelta(days=1)
        )


def test_adicionar_exercicio_sem_nome_nem_aula_e_recusado(aluno):
    treino = servicos.prescrever_treino(aluno=aluno, nome="Treino")
    with pytest.raises(ErroDeTreino):
        servicos.adicionar_exercicio(treino=treino, nome="   ")


def test_reordenar_exige_a_lista_completa(aluno):
    treino = servicos.prescrever_treino(
        aluno=aluno, nome="Treino", exercicios=[{"nome": "A"}, {"nome": "B"}]
    )
    identificadores = [item.pk for item in treino.exercicios.all()]
    with pytest.raises(ErroDeTreino):
        servicos.reordenar_exercicios(treino, [identificadores[0]])
    servicos.reordenar_exercicios(treino, list(reversed(identificadores)))
    assert [item.nome for item in treino.exercicios.all()] == ["B", "A"]


def test_duplicar_treino_nao_copia_historico(aluno, outro_aluno):
    treino = servicos.prescrever_treino(
        aluno=aluno, nome="Original", exercicios=[{"nome": "Agachamento"}]
    )
    exercicio = treino.exercicios.first()
    servicos.registrar_execucao(exercicio=exercicio, carga=Decimal("60.00"))
    copia = servicos.duplicar_treino(treino=treino, aluno=outro_aluno, nome="Copiado")
    assert copia.aluno == outro_aluno
    assert copia.exercicios.count() == 1
    assert copia.exercicios.first().execucoes.count() == 0
    assert copia.situacao == Treino.Situacao.RASCUNHO


def test_registrar_execucao_e_medir_progresso(aluno):
    treino = servicos.prescrever_treino(
        aluno=aluno, nome="Forca", exercicios=[{"nome": "Leg press"}]
    )
    exercicio = treino.exercicios.first()
    hoje = timezone.localdate()
    servicos.registrar_execucao(
        exercicio=exercicio, carga=Decimal("80.00"), data=hoje - timedelta(days=20)
    )
    servicos.registrar_execucao(
        exercicio=exercicio, carga=Decimal("100.00"), data=hoje, esforco_percebido=8
    )
    progresso = servicos.progresso_do_exercicio(exercicio)
    assert progresso["execucoes"] == 2
    assert progresso["variacao"] == Decimal("20.00")
    assert progresso["variacao_percentual"] == 25.0


def test_esforco_percebido_fora_da_escala_e_recusado(aluno):
    treino = servicos.prescrever_treino(aluno=aluno, nome="Forca", exercicios=[{"nome": "X"}])
    with pytest.raises(ErroDeTreino):
        servicos.registrar_execucao(
            exercicio=treino.exercicios.first(), carga=10, esforco_percebido=15
        )


def test_avaliacao_calcula_imc_e_faixa(aluno):
    avaliacao = servicos.registrar_avaliacao(
        aluno=aluno,
        peso=Decimal("82.00"),
        altura=Decimal("1.80"),
        percentual_de_gordura=Decimal("18.5"),
        medidas={"cintura": "88", "quadril": "100", "inventado": "50"},
    )
    assert avaliacao.imc == Decimal("25.31")
    assert avaliacao.faixa_de_imc == "sobrepeso"
    assert set(avaliacao.medidas) == {"cintura", "quadril"}, "medida desconhecida e ignorada"
    assert ("Cintura", "88") in [(rotulo, valor) for rotulo, valor in avaliacao.medidas_legiveis()]


def test_uma_avaliacao_por_dia(aluno):
    hoje = timezone.localdate()
    servicos.registrar_avaliacao(aluno=aluno, peso=80, altura=1.75, data=hoje)
    with pytest.raises(ErroDeTreino):
        servicos.registrar_avaliacao(aluno=aluno, peso=79, altura=1.75, data=hoje)


def test_evolucao_compara_primeira_e_ultima(aluno):
    hoje = timezone.localdate()
    servicos.registrar_avaliacao(
        aluno=aluno,
        peso=Decimal("85.00"),
        altura=Decimal("1.75"),
        percentual_de_gordura=Decimal("25.0"),
        medidas={"cintura": "95"},
        data=hoje - timedelta(days=60),
    )
    servicos.registrar_avaliacao(
        aluno=aluno,
        peso=Decimal("80.00"),
        altura=Decimal("1.75"),
        percentual_de_gordura=Decimal("20.0"),
        medidas={"cintura": "88"},
        data=hoje,
    )
    evolucao = servicos.evolucao_do_aluno(aluno)
    assert evolucao["diferencas"]["peso"] == Decimal("-5.00")
    assert evolucao["diferencas"]["percentual_de_gordura"] == Decimal("-5.0")
    cintura = next(linha for linha in evolucao["medidas"] if linha["chave"] == "cintura")
    assert cintura["diferenca"] == Decimal("-7")
    assert len(evolucao["series"]["peso"]) == 2


def test_evolucao_sem_avaliacao_nao_quebra(aluno):
    evolucao = servicos.evolucao_do_aluno(aluno)
    assert evolucao["avaliacoes"] == [] and evolucao["diferencas"] == {}


def test_exercicio_aponta_conflito_com_a_ficha_de_saude(aluno, ficha):
    from aulas.models import Aulas

    aula_com_restricao = Aulas.todos.create(
        rede=aluno.rede,
        unidade=aluno.unidade,
        nome="Alongamento de coluna",
        descricao="Cuidado com a coluna",
        professor=aluno.user,
        categorias_exercicios="flexibilidade",
        restricao="coluna",
    )
    treino = servicos.prescrever_treino(aluno=aluno, nome="Mobilidade")
    exercicio = servicos.adicionar_exercicio(treino=treino, nome="", aula=aula_com_restricao)
    assert exercicio.nome == "Alongamento de coluna"
    assert exercicio.tem_restricao_conflitante is True


def test_reordenar_de_verdade_reordena(aluno):
    treino = servicos.prescrever_treino(
        aluno=aluno, nome="Ordem", exercicios=[{"nome": "Primeiro"}, {"nome": "Segundo"}]
    )
    identificadores = [item.pk for item in treino.exercicios.all()]
    servicos.reordenar_exercicios(treino, list(reversed(identificadores)))
    assert [item.nome for item in treino.exercicios.all()] == ["Segundo", "Primeiro"]
