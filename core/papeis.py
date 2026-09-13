"""Papeis e escopos de acesso (RBAC por rede e por unidade)."""

from django.db import models


class Papel(models.TextChoices):
    SUPERADMIN_PLATAFORMA = "superadmin_plataforma", "Superadmin da plataforma"
    ADMIN_REDE = "admin_rede", "Administrador da rede"
    GESTOR_UNIDADE = "gestor_unidade", "Gestor de unidade"
    RECEPCAO = "recepcao", "Recepcao"
    PROFESSOR = "professor", "Professor"
    FINANCEIRO_REDE = "financeiro_rede", "Financeiro da rede"
    AUDITOR_REDE = "auditor_rede", "Auditor da rede"
    ALUNO = "aluno", "Aluno"


#: Papeis que enxergam todas as unidades da rede.
PAPEIS_DA_REDE = frozenset(
    {
        Papel.SUPERADMIN_PLATAFORMA,
        Papel.ADMIN_REDE,
        Papel.FINANCEIRO_REDE,
        Papel.AUDITOR_REDE,
    }
)

#: Papeis que operam dentro de uma unidade.
PAPEIS_DA_UNIDADE = frozenset(
    {
        Papel.GESTOR_UNIDADE,
        Papel.RECEPCAO,
        Papel.PROFESSOR,
        Papel.ALUNO,
    }
)

#: Papeis que podem escrever dados de negocio.
PAPEIS_ESCRITA = frozenset(
    {
        Papel.SUPERADMIN_PLATAFORMA,
        Papel.ADMIN_REDE,
        Papel.GESTOR_UNIDADE,
        Papel.RECEPCAO,
    }
)

ESCOPO_SEPARADOR = " "


def tem_papel_de_rede(papeis) -> bool:
    """Diz se algum dos papeis informados enxerga a rede inteira."""
    if isinstance(papeis, str):
        papeis = [papeis]
    return bool(PAPEIS_DA_REDE.intersection(papeis))


class StatusRede(models.TextChoices):
    TRIAL = "trial", "Em teste"
    ATIVO = "ativo", "Ativo"
    INADIMPLENTE = "inadimplente", "Inadimplente"
    SOMENTE_LEITURA = "somente_leitura", "Somente leitura"
    SUSPENSO = "suspenso", "Suspenso"
    CANCELADO = "cancelado", "Cancelado"


class StatusUnidade(models.TextChoices):
    ATIVA = "ativa", "Ativa"
    INATIVA = "inativa", "Inativa"
    IMPLANTACAO = "em_implantacao", "Em implantacao"


class TipoUnidade(models.TextChoices):
    MATRIZ = "propria", "Propria"
    FRANQUEADA = "franqueada", "Franqueada"
    LICENCIADA = "licenciada", "Licenciada"
