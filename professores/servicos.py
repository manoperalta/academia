"""Regras do cadastro de professor.

Fonte unica usada pela tela do dashboard (Bootstrap, igual ao cadastro de aluno) e pelo
painel de gestao (Tailwind): assim as duas cascas nunca divergem na regra de negocio.

Regras que vivem aqui:
- o acesso (login) do professor nasce junto com o cadastro;
- o professor atende **uma ou mais unidades** da rede -- isso e um ``VinculoUsuario``
  por unidade (papel ``PROFESSOR``), o que permite abrir agenda em cada unidade;
- o valor da hora e gravado na regra vigente de remuneracao do professor.
"""

from __future__ import annotations

from django.db.models import Q

from core.models import Unidade
from core.papeis import Papel
from core.tenancy import VinculoUsuario


class ErroDeProfessor(Exception):
    """Falha esperada do cadastro de professor."""


def unidades_da_rede(rede):
    """Unidades ativas da rede, para o seletor de unidades de atendimento."""
    if rede is None:
        return Unidade.todos.none()
    return Unidade.todos.filter(rede=rede).order_by("nome")


def unidades_do_professor(professor):
    """Unidades em que o professor atende, pelos vinculos ativos."""
    if professor is None or professor.user_id is None or professor.rede_id is None:
        return Unidade.todos.none()
    return Unidade.todos.filter(
        vinculos__usuario_id=professor.user_id,
        vinculos__rede_id=professor.rede_id,
        vinculos__papel=Papel.PROFESSOR,
        vinculos__ativo=True,
    ).distinct().order_by("nome")


def sincronizar_unidades(professor, unidades, *, unidade_principal=None) -> list:
    """Alinha os vinculos do professor as unidades escolhidas.

    Cria o que falta, reativa o que voltou e **desativa** (nunca apaga) o que saiu -- o
    historico de agenda/turmas da unidade continua valido. Devolve as unidades efetivas.
    """
    escolhidas = list(unidades)
    if professor.user_id is None:
        return []

    atuais = list(
        VinculoUsuario.todos.filter(
            usuario_id=professor.user_id,
            rede_id=professor.rede_id,
            papel=Papel.PROFESSOR,
        )
    )
    ids_escolhidos = {unidade.pk for unidade in escolhidas}
    for vinculo in atuais:
        deve_estar_ativo = vinculo.unidade_id in ids_escolhidos
        if vinculo.ativo != deve_estar_ativo:
            vinculo.ativo = deve_estar_ativo
            vinculo.save(update_fields=["ativo"])

    ja_existem = {vinculo.unidade_id for vinculo in atuais}
    for unidade in escolhidas:
        if unidade.pk in ja_existem:
            continue
        VinculoUsuario.todos.create(
            usuario_id=professor.user_id,
            rede=professor.rede,
            unidade=unidade,
            papel=Papel.PROFESSOR,
            ativo=True,
        )

    principal = unidade_principal or (escolhidas[0] if escolhidas else None)
    if principal is not None and professor.unidade_id != principal.pk:
        professor.unidade = principal
        professor.save(update_fields=["unidade"])
    return escolhidas


def aplicar_valor_por_hora(professor, valor) -> None:
    """Grava o valor da hora na regra vigente do professor (em branco nao mexe)."""
    if valor is None or professor.pk is None:
        return
    if valor != professor.valor_por_hora:
        professor.definir_valor_por_hora(valor)


def unidades_do_atendimento(professor):
    """Unidades em que este professor pode abrir agenda.

    Junta os vinculos ativos do usuario com a unidade em que ele foi cadastrado: um
    professor pode atender varias unidades (ou uma so) e a agenda e aberta por unidade.
    """
    if professor is None:
        return Unidade.todos.none()
    filtro = Q(pk__in=[])
    usuario = getattr(professor, "user", None)
    if usuario is not None and usuario.pk:
        filtro |= Q(vinculos__usuario=usuario, vinculos__ativo=True)
    if getattr(professor, "unidade_id", None):
        filtro |= Q(pk=professor.unidade_id)
    return Unidade.todos.filter(filtro).distinct().order_by("nome")
