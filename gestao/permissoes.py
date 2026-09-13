"""RBAC do painel: papel x modulo x nivel de acesso (PRD secao 7.1)."""

from __future__ import annotations

from django.db import models

from core.context import rede_atual
from core.models import VinculoUsuario
from core.papeis import Papel


class Modulo(models.TextChoices):
    """Modulos do painel do tenant (PRD secao 7.2)."""

    VISAO_GERAL = "visao_geral", "Visao geral"
    ALUNOS = "alunos", "Alunos"
    PROFESSORES = "professores", "Professores"
    AULAS = "aulas", "Aulas e videos"
    AGENDA = "agenda", "Agenda e paineis"
    FINANCEIRO = "financeiro", "Financeiro"
    RELATORIOS = "relatorios", "Relatorios"
    COMUNICACAO = "comunicacao", "Comunicacao"
    IDENTIDADE = "identidade", "Identidade e dados fiscais"
    EQUIPE = "equipe", "Equipe e acessos"
    PLANO = "plano", "Meu plano"
    PRIVACIDADE = "privacidade", "Privacidade e LGPD"
    DOMINIO = "dominio", "Domínio e endereço"
    AUDITORIA = "auditoria", "Auditoria"
    REDE = "rede", "Painel da rede"
    UNIDADES = "unidades", "Unidades"
    REPASSES = "repasses", "Repasses e royalties"
    GOVERNANCA = "governanca", "Governança da rede"
    COMUNICADOS = "comunicados", "Comunicados"
    APROVACOES = "aprovacoes", "Alçadas e aprovações"
    CATALOGO = "catalogo", "Catálogo da rede"
    CRM = "crm", "CRM e captacao"
    RETENCAO = "retencao", "Retencao de alunos"
    ACESSO = "acesso", "Controle de acesso"
    COBRANCA = "cobranca", "Cobranca recorrente"
    FISCAL = "fiscal", "Fiscal (NFS-e)"
    PDV = "pdv", "PDV e estoque"
    PARCEIROS = "parceiros", "Parceiros e conciliacao"
    COMISSOES = "comissoes", "Comissoes e remuneracao"
    GAMIFICACAO = "gamificacao", "Gamificacao"
    PESQUISAS = "pesquisas", "Pesquisas e NPS"


NIVEIS: dict[str | None, int] = {None: 0, "ver": 1, "editar": 2, "admin": 3}

TUDO = dict.fromkeys(Modulo, "admin")
SO_LEITURA = dict.fromkeys(Modulo, "ver")

#: Matriz papel x modulo. Nivel: ver < editar < admin.
MATRIZ: dict[str, dict[str, str]] = {
    Papel.SUPERADMIN_PLATAFORMA: TUDO,
    Papel.ADMIN_REDE: TUDO,
    Papel.GESTOR_UNIDADE: {
        Modulo.VISAO_GERAL: "ver",
        Modulo.ALUNOS: "editar",
        Modulo.PROFESSORES: "editar",
        Modulo.AULAS: "editar",
        Modulo.AGENDA: "editar",
        Modulo.FINANCEIRO: "ver",
        Modulo.RELATORIOS: "ver",
        Modulo.COMUNICACAO: "ver",
        Modulo.IDENTIDADE: "ver",
        Modulo.EQUIPE: "editar",
        Modulo.PLANO: "admin",
        Modulo.AUDITORIA: "ver",
        Modulo.PRIVACIDADE: "ver",
        Modulo.CRM: "editar",
        Modulo.ACESSO: "editar",
        Modulo.COBRANCA: "editar",
        Modulo.FISCAL: "editar",
        Modulo.PDV: "editar",
        Modulo.PARCEIROS: "editar",
        Modulo.RETENCAO: "editar",
        Modulo.COMISSOES: "ver",
        Modulo.GAMIFICACAO: "ver",
        Modulo.PESQUISAS: "ver",
        Modulo.REDE: "ver",
        Modulo.UNIDADES: "ver",
        Modulo.REPASSES: "ver",
        Modulo.COMUNICADOS: "editar",
        Modulo.APROVACOES: "editar",
        Modulo.CATALOGO: "editar",
    },
    Papel.RECEPCAO: {
        Modulo.VISAO_GERAL: "ver",
        Modulo.ALUNOS: "editar",
        Modulo.AGENDA: "editar",
        Modulo.PROFESSORES: "ver",
        Modulo.AULAS: "ver",
        Modulo.FINANCEIRO: "ver",
        Modulo.COMUNICADOS: "ver",
    },
    Papel.PROFESSOR: {
        Modulo.VISAO_GERAL: "ver",
        Modulo.ALUNOS: "ver",
        Modulo.AULAS: "editar",
        Modulo.AGENDA: "editar",
    },
    Papel.FINANCEIRO_REDE: {
        Modulo.VISAO_GERAL: "ver",
        Modulo.ALUNOS: "ver",
        Modulo.PROFESSORES: "ver",
        Modulo.FINANCEIRO: "editar",
        Modulo.PLANO: "ver",
        Modulo.RELATORIOS: "ver",
        Modulo.AUDITORIA: "ver",
        Modulo.REPASSES: "editar",
        Modulo.COMUNICADOS: "ver",
    },
    Papel.AUDITOR_REDE: SO_LEITURA,
    Papel.ALUNO: {},
}


def nivel_do_papel(papel: str, modulo: str) -> int:
    """Nivel que um papel tem em um modulo (0 = sem acesso)."""
    return NIVEIS.get(MATRIZ.get(papel, {}).get(modulo), 0)


def papeis_do_usuario(usuario, rede=None, unidade=None) -> set[str]:
    """Papeis ativos do usuario na rede (e opcionalmente na unidade) informada."""
    if not getattr(usuario, "is_authenticated", False):
        return set()
    if getattr(usuario, "is_superuser", False):
        return {Papel.SUPERADMIN_PLATAFORMA}
    if getattr(usuario, "is_staff", False):
        # Equipe da SafeStack: inclui o acesso de suporte (impersonation) auditado.
        return {Papel.SUPERADMIN_PLATAFORMA}
    consulta = VinculoUsuario.todos.filter(usuario=usuario, ativo=True)
    if rede is not None:
        consulta = consulta.filter(rede=rede)
    if unidade is not None:
        consulta = consulta.filter(models.Q(unidade=unidade) | models.Q(unidade__isnull=True))
    return set(consulta.values_list("papel", flat=True))


def nivel(usuario, modulo: str, rede=None, unidade=None) -> int:
    """Maior nivel do usuario no modulo, considerando todos os papeis ativos."""
    rede = rede or rede_atual()
    papeis = papeis_do_usuario(usuario, rede=rede if rede else None, unidade=unidade)
    return max((nivel_do_papel(papel, modulo) for papel in papeis), default=0)


def pode(usuario, modulo: str, minimo: str = "ver", rede=None, unidade=None) -> bool:
    """True se o usuario tem ao menos o nivel pedido no modulo."""
    return nivel(usuario, modulo, rede=rede, unidade=unidade) >= NIVEIS[minimo]


def pode_editar(usuario, modulo: str, **kwargs) -> bool:
    return pode(usuario, modulo, "editar", **kwargs)


def modulos_visiveis(usuario, rede=None, unidade=None) -> list[Modulo]:
    """Modulos que o usuario pode ao menos visualizar (ordem de exibicao)."""
    return [m for m in Modulo if pode(usuario, m.value, "ver", rede=rede, unidade=unidade)]
