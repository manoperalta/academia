"""Servicos do painel do professor: agenda, turma, presenca, alunos e comissoes.

O professor enxerga **apenas o que e dele** — as turmas em que e responsavel, os alunos dessas turmas
e os treinos que prescreveu. E o mesmo principio do escopo por rede, um nivel abaixo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from agendamento.models import Agendamento
from painel.models import Painel
from painel_do_professor.models import OcorrenciaDaTurma, SubstituicaoDeTurma
from professores.models import Professor
from treinos.models import AvaliacaoFisica, Treino
from usuarios.models import Usuario

SITUACOES_DE_PRESENCA = {"presente": "presente", "falta": "falta", "cancelado": "cancelado"}


class ErroDoProfessor(Exception):
    """Falha esperada no painel do professor."""


def professor_do_usuario(usuario, rede=None) -> Professor | None:
    """Liga o login ao perfil de professor (o vinculo e pelo OneToOne ``user``)."""
    consulta = Professor.todos.filter(user=usuario)
    if rede is not None:
        consulta = consulta.filter(rede=rede)
    return consulta.first()


def turmas_do_professor(professor, de: date | None = None, ate: date | None = None):
    """Turmas em que ele e responsavel (ou substituto registrado)."""
    consulta = Painel.objects.filter(
        responsavel=professor.user, arquivado_em__isnull=True
    ).select_related("unidade")
    if de is not None:
        consulta = consulta.filter(data__gte=de)
    if ate is not None:
        consulta = consulta.filter(data__lte=ate)
    return consulta.order_by("data", "hora_inicio")


def agenda_do_dia(professor, dia: date | None = None) -> dict:
    dia = dia or timezone.localdate()
    turmas = list(turmas_do_professor(professor, de=dia, ate=dia))
    agendamentos = Agendamento.objects.filter(
        painel__in=turmas, arquivado_em__isnull=True
    ).select_related("aluno", "painel")
    por_turma = {}
    for agendamento in agendamentos:
        por_turma.setdefault(agendamento.painel_id, []).append(agendamento)
    return {
        "dia": dia,
        "turmas": [
            {
                "turma": turma,
                "aulas": [item.aula for item in turma.itens.select_related("aula")],
                "agendamentos": por_turma.get(turma.pk, []),
                "ocupacao": len(por_turma.get(turma.pk, [])),
                "capacidade": turma.numero_de_user,
            }
            for turma in turmas
        ],
        "total_de_alunos": agendamentos.count(),
        "presencas": agendamentos.filter(status="presente").count(),
        "faltas": agendamentos.filter(status="falta").count(),
    }


def semana_do_professor(professor, inicio: date | None = None) -> list[dict]:
    inicio = inicio or (timezone.localdate() - timedelta(days=timezone.localdate().weekday()))
    dias = []
    for deslocamento in range(7):
        dia = inicio + timedelta(days=deslocamento)
        agenda = agenda_do_dia(professor, dia)
        dias.append({"dia": dia, "turmas": agenda["turmas"], "alunos": agenda["total_de_alunos"]})
    return dias


def marcar_presenca(
    *, agendamento: Agendamento, situacao: str, professor: Professor
) -> Agendamento:
    """O professor fecha a chamada; so mexe em agendamento das proprias turmas."""
    if situacao not in SITUACOES_DE_PRESENCA:
        raise ErroDoProfessor("Situacao de presenca desconhecida.")
    if agendamento.painel.responsavel_id != professor.user_id:
        raise ErroDoProfessor("Esta turma nao e sua.")
    agendamento.status = situacao
    agendamento.save(update_fields=["status"])
    return agendamento


def chamada_do_dia(*, turma: Painel, professor: Professor, presencas: dict) -> dict:
    """Fecha a chamada de uma turma de uma vez (id por id)."""
    if turma.responsavel_id != professor.user_id:
        raise ErroDoProfessor("Esta turma nao e sua.")
    atualizados = 0
    for agendamento in Agendamento.objects.filter(painel=turma, arquivado_em__isnull=True):
        situacao = presencas.get(str(agendamento.pk))
        if situacao in SITUACOES_DE_PRESENCA:
            agendamento.status = situacao
            agendamento.save(update_fields=["status"])
            atualizados += 1
    return {"turma": turma, "atualizados": atualizados}


def registrar_ocorrencia(
    *, turma: Painel, aluno: Usuario, professor: Professor, tipo: str, descricao: str
) -> OcorrenciaDaTurma:
    if not (descricao or "").strip():
        raise ErroDoProfessor("Descreva a ocorrencia.")
    if tipo not in dict(OcorrenciaDaTurma.Tipo.choices):
        raise ErroDoProfessor("Tipo de ocorrencia desconhecido.")
    return OcorrenciaDaTurma.objects.create(
        turma=turma, aluno=aluno, professor=professor, tipo=tipo, descricao=descricao.strip()
    )


@transaction.atomic
def registrar_substituicao(
    *, turma: Painel, substituto: Professor, motivo: str = ""
) -> SubstituicaoDeTurma:
    """Transfere a turma para outro professor, deixando o rastro de quem assumiu por que."""
    titular = professor_do_usuario(turma.responsavel, rede=turma.rede)
    if titular is None:
        raise ErroDoProfessor("A turma nao tem professor responsavel cadastrado.")
    if substituto.pk == titular.pk:
        raise ErroDoProfessor("O substituto tem de ser outro professor.")
    substituicao = SubstituicaoDeTurma.objects.create(
        turma=turma, titular=titular, substituto=substituto, motivo=motivo[:200]
    )
    turma.responsavel = substituto.user
    turma.save(update_fields=["responsavel"])
    return substituicao


def ocorrencias_da_turma(turma: Painel, limite: int = 50):
    return turma.ocorrencias.select_related("aluno").order_by("-criado_em")[:limite]


# ------------------------------------------------------------------ alunos
def meus_alunos(professor, limite: int = 200):
    """Alunos que aparecem nas minhas turmas ou nos treinos que prescrevi."""
    das_turmas = Agendamento.objects.filter(
        painel__responsavel=professor.user, arquivado_em__isnull=True
    ).values_list("aluno_id", flat=True)
    dos_treinos = Treino.objects.filter(professor=professor).values_list(
        "aluno__user_id", flat=True
    )
    identificadores = set(das_turmas) | set(dos_treinos)
    return Usuario.todos.filter(rede=professor.rede, user_id__in=identificadores)[:limite]


def frequencia_do_aluno(aluno, dias: int = 90) -> dict:
    desde = timezone.now() - timedelta(days=dias)
    agendamentos = Agendamento.objects.filter(
        aluno=aluno.user, data_agendamento__gte=desde, arquivado_em__isnull=True
    )
    total = agendamentos.count()
    presencas = agendamentos.filter(status="presente").count()
    return {
        "dias": dias,
        "agendamentos": total,
        "presencas": presencas,
        "faltas": agendamentos.filter(status="falta").count(),
        "taxa_de_presenca": round(presencas * 100 / total, 1) if total else 0.0,
    }


def avaliacoes_do_aluno(aluno, limite: int = 24):
    return AvaliacaoFisica.objects.filter(aluno=aluno)[:limite]


# ------------------------------------------------------------------ comissoes
def minhas_comissoes(professor, limite: int = 24) -> dict:
    """Extrato do proprio trabalho: apuracoes por competencia e quanto ja foi pago."""
    from remuneracao.models import ApuracaoDeComissao

    apuracoes = (
        ApuracaoDeComissao.objects.filter(professor=professor)
        .select_related("unidade")
        .order_by("-inicio")[:limite]
    )
    total = Decimal("0")
    pago = Decimal("0")
    for apuracao in apuracoes:
        total += apuracao.valor_devido or Decimal("0")
        if getattr(apuracao, "pago_em", None):
            pago += apuracao.valor_devido or Decimal("0")
    return {
        "apuracoes": list(apuracoes),
        "total_devido": total,
        "total_pago": pago,
        "a_receber": total - pago,
    }
