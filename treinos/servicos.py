"""Servicos de treino e avaliacao: prescrever, duplicar, registrar execucao e medir evolucao."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from treinos.models import (
    MEDIDAS,
    AvaliacaoFisica,
    ExecucaoDoExercicio,
    ExercicioDoTreino,
    Treino,
)


class ErroDeTreino(Exception):
    """Falha esperada no fluxo de treino ou avaliacao."""


# ------------------------------------------------------------------ prescricao
@transaction.atomic
def prescrever_treino(
    *,
    aluno,
    professor=None,
    nome: str,
    objetivo: str = "condicionamento",
    exercicios: list[dict] | None = None,
    observacoes: str = "",
    inicio: date | None = None,
    fim: date | None = None,
    ativar: bool = True,
) -> Treino:
    """Cria o treino do aluno com os exercicios na ordem informada."""
    if not (nome or "").strip():
        raise ErroDeTreino("Dê um nome ao treino.")
    if objetivo not in dict(Treino.Objetivo.choices):
        raise ErroDeTreino("Objetivo de treino desconhecido.")
    if inicio and fim and fim < inicio:
        raise ErroDeTreino("A data final nao pode ser antes do inicio.")
    treino = Treino.objects.create(
        rede=aluno.rede,
        unidade=aluno.unidade,
        aluno=aluno,
        professor=professor,
        nome=nome.strip(),
        objetivo=objetivo,
        observacoes=observacoes,
        inicio=inicio,
        fim=fim,
        situacao=Treino.Situacao.ATIVO if ativar else Treino.Situacao.RASCUNHO,
    )
    for posicao, dados in enumerate(exercicios or [], start=1):
        adicionar_exercicio(
            treino=treino,
            ordem=dados.get("ordem") or posicao,
            **{
                chave: dados[chave]
                for chave in (
                    "nome",
                    "series",
                    "repeticoes",
                    "carga_sugerida",
                    "descanso_segundos",
                    "aula",
                    "observacoes",
                )
                if chave in dados
            },
        )
    return treino


def adicionar_exercicio(
    *,
    treino: Treino,
    nome: str,
    series: int = 3,
    repeticoes: str = "12",
    carga_sugerida=Decimal("0"),
    descanso_segundos: int = 60,
    ordem: int | None = None,
    aula=None,
    observacoes: str = "",
) -> ExercicioDoTreino:
    if treino.situacao == Treino.Situacao.CANCELADO:
        raise ErroDeTreino("Treino cancelado nao recebe exercicio.")
    if not (nome or "").strip() and aula is None:
        raise ErroDeTreino("Informe o exercicio ou escolha uma videoaula.")
    if series <= 0:
        raise ErroDeTreino("Series precisam ser maior que zero.")
    if ordem is None:
        ordem = (treino.exercicios.count() or 0) + 1
    return ExercicioDoTreino.objects.create(
        treino=treino,
        aula=aula,
        nome=(nome or getattr(aula, "nome", "")).strip(),
        series=series,
        repeticoes=repeticoes,
        carga_sugerida=carga_sugerida,
        descanso_segundos=descanso_segundos,
        ordem=ordem,
        observacoes=observacoes,
    )


def reordenar_exercicios(treino: Treino, ordem_dos_ids: list[int]) -> Treino:
    """Recebe a ordem nova e regrava a posicao de cada exercicio."""
    atuais = {exercicio.pk: exercicio for exercicio in treino.exercicios.all()}
    if set(ordem_dos_ids) != set(atuais):
        raise ErroDeTreino("A ordem enviada nao corresponde aos exercicios do treino.")
    for posicao, identificador in enumerate(ordem_dos_ids, start=1):
        exercicio = atuais[identificador]
        exercicio.ordem = posicao
        exercicio.save(update_fields=["ordem"])
    return treino


def encerrar_treino(treino: Treino, situacao: str) -> Treino:
    if situacao not in dict(Treino.Situacao.choices):
        raise ErroDeTreino("Situacao de treino desconhecida.")
    treino.situacao = situacao
    treino.save(update_fields=["situacao"])
    return treino


def duplicar_treino(*, treino: Treino, aluno=None, nome: str = "") -> Treino:
    """Copia a prescricao para outro aluno (ou renova para o mesmo) sem carregar o historico."""
    novo = Treino.objects.create(
        rede=treino.rede,
        unidade=treino.unidade,
        aluno=aluno or treino.aluno,
        professor=treino.professor,
        nome=(nome or f"{treino.nome} (copia)")[:120],
        objetivo=treino.objetivo,
        observacoes=treino.observacoes,
        inicio=treino.inicio,
        fim=treino.fim,
        situacao=Treino.Situacao.RASCUNHO,
    )
    for exercicio in treino.exercicios.all():
        ExercicioDoTreino.objects.create(
            treino=novo,
            aula=exercicio.aula,
            nome=exercicio.nome,
            series=exercicio.series,
            repeticoes=exercicio.repeticoes,
            carga_sugerida=exercicio.carga_sugerida,
            descanso_segundos=exercicio.descanso_segundos,
            ordem=exercicio.ordem,
            observacoes=exercicio.observacoes,
        )
    return novo


# ------------------------------------------------------------------ execucao
def registrar_execucao(
    *,
    exercicio: ExercicioDoTreino,
    carga,
    repeticoes: str = "",
    esforco_percebido: int = 0,
    data: date | None = None,
    observacoes: str = "",
) -> ExecucaoDoExercicio:
    """Anota o que o aluno fez — e o que permite o professor ajustar a carga depois."""
    if esforco_percebido and not 1 <= int(esforco_percebido) <= 10:
        raise ErroDeTreino("O esforco percebido vai de 1 a 10.")
    momento = data or timezone.localdate()
    return ExecucaoDoExercicio.objects.create(
        exercicio=exercicio,
        data=momento,
        carga=carga,
        repeticoes=repeticoes,
        esforco_percebido=esforco_percebido or 0,
        observacoes=observacoes,
    )


def progresso_do_exercicio(exercicio: ExercicioDoTreino) -> dict:
    execucoes = list(exercicio.execucoes.order_by("data"))
    if not execucoes:
        return {
            "execucoes": 0,
            "primeira": None,
            "ultima": None,
            "variacao": Decimal("0"),
            "variacao_percentual": 0.0,
        }
    primeira, ultima = execucoes[0], execucoes[-1]
    variacao = (ultima.carga or Decimal("0")) - (primeira.carga or Decimal("0"))
    base = primeira.carga or Decimal("0")
    return {
        "execucoes": len(execucoes),
        "primeira": primeira,
        "ultima": ultima,
        "variacao": variacao,
        "variacao_percentual": round(float(variacao) * 100 / float(base), 1) if base else 0.0,
    }


# ------------------------------------------------------------------ avaliacao fisica
def _numero(valor, casas: int = 2) -> Decimal:
    try:
        return Decimal(str(valor or 0)).quantize(Decimal("1." + "0" * casas))
    except InvalidOperation as erro:
        raise ErroDeTreino(f"Valor numerico invalido: {valor!r}") from erro


def _texto_de_medida(valor, casas: int = 1) -> str:
    """Medida em texto curto: 88 vira "88", e 88.5 continua "88.5"."""
    numero = _numero(valor, casas)
    if numero == numero.to_integral_value():
        return str(int(numero))
    return str(numero)


def registrar_avaliacao(
    *,
    aluno,
    data: date | None = None,
    peso=0,
    altura=0,
    percentual_de_gordura=0,
    massa_muscular=0,
    medidas: dict | None = None,
    avaliador=None,
    observacoes: str = "",
) -> AvaliacaoFisica:
    """Guarda a avaliacao do dia (uma por dia por aluno) com as medidas informadas."""
    momento = data or timezone.localdate()
    if AvaliacaoFisica.objects.filter(aluno=aluno, data=momento).exists():
        raise ErroDeTreino("Ja existe avaliacao deste aluno nesta data.")
    limpas = {}
    for chave, valor in (medidas or {}).items():
        if chave not in dict(MEDIDAS) or valor in (None, ""):
            continue
        limpas[chave] = _texto_de_medida(valor, 1)
    avaliacao = AvaliacaoFisica.objects.create(
        rede=aluno.rede,
        unidade=aluno.unidade,
        aluno=aluno,
        avaliador=avaliador,
        data=momento,
        peso=_numero(peso),
        altura=_numero(altura),
        percentual_de_gordura=_numero(percentual_de_gordura, 1),
        massa_muscular=_numero(massa_muscular),
        medidas=limpas,
        observacoes=observacoes,
    )
    return avaliacao


def evolucao_do_aluno(aluno, limite: int = 12) -> dict:
    """Compara a primeira e a ultima avaliacao e monta a serie para a tela de evolucao."""
    avaliacoes = list(AvaliacaoFisica.objects.filter(aluno=aluno).order_by("data")[:limite])
    if not avaliacoes:
        return {
            "avaliacoes": [],
            "primeira": None,
            "ultima": None,
            "diferencas": {},
            "medidas": [],
            "series": {},
        }
    primeira, ultima = avaliacoes[0], avaliacoes[-1]
    diferencas = {
        "peso": (ultima.peso or Decimal("0")) - (primeira.peso or Decimal("0")),
        "percentual_de_gordura": (
            (ultima.percentual_de_gordura or Decimal("0"))
            - (primeira.percentual_de_gordura or Decimal("0"))
        ),
        "massa_muscular": (
            (ultima.massa_muscular or Decimal("0")) - (primeira.massa_muscular or Decimal("0"))
        ),
        "imc": (ultima.imc or Decimal("0")) - (primeira.imc or Decimal("0")),
    }
    linhas = []
    for chave, rotulo in MEDIDAS:
        inicio = (primeira.medidas or {}).get(chave)
        fim = (ultima.medidas or {}).get(chave)
        if inicio or fim:
            linhas.append(
                {
                    "rotulo": rotulo,
                    "chave": chave,
                    "inicio": inicio,
                    "fim": fim,
                    "diferenca": (Decimal(str(fim or 0)) - Decimal(str(inicio or 0))),
                }
            )
    series = {
        "peso": [{"data": item.data, "valor": item.peso} for item in avaliacoes],
        "percentual_de_gordura": [
            {"data": item.data, "valor": item.percentual_de_gordura} for item in avaliacoes
        ],
    }
    return {
        "avaliacoes": avaliacoes,
        "primeira": primeira,
        "ultima": ultima,
        "diferencas": diferencas,
        "medidas": linhas,
        "series": series,
    }


def resumo_do_aluno(aluno) -> dict:
    """O que o professor quer ver de relance sobre o aluno na ficha."""
    from agendamento.models import Agendamento

    treinos = Treino.objects.filter(aluno=aluno)
    agendamentos = Agendamento.objects.filter(aluno=aluno.user, arquivado_em__isnull=True)
    avaliacoes = AvaliacaoFisica.objects.filter(aluno=aluno)
    return {
        "treinos_ativos": treinos.filter(situacao=Treino.Situacao.ATIVO).count(),
        "treinos_total": treinos.count(),
        "agendamentos": agendamentos.count(),
        "presencas": agendamentos.filter(status="Concluido").count(),
        "faltas": agendamentos.filter(status="Faltou").count(),
        "avaliacoes": avaliacoes.count(),
        "ultima_avaliacao": avaliacoes.order_by("-data").first(),
    }
