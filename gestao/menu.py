"""Mapa dos modulos do painel para as rotas (usado pelo menu e pelos testes)."""
from gestao.permissoes import Modulo

ROTAS: dict[str, str] = {
    Modulo.VISAO_GERAL: "gestao:visao_geral",
    Modulo.ALUNOS: "gestao:alunos",
    Modulo.PROFESSORES: "gestao:professores",
    Modulo.AULAS: "gestao:aulas",
    Modulo.AGENDA: "gestao:agenda",
    Modulo.FINANCEIRO: "gestao:financeiro",
    Modulo.RELATORIOS: "gestao:relatorios",
    Modulo.COMUNICACAO: "gestao:comunicacao",
    Modulo.IDENTIDADE: "gestao:identidade",
    Modulo.EQUIPE: "gestao:equipe",
    Modulo.PLANO: "gestao:plano",
    Modulo.AUDITORIA: "gestao:auditoria",
}
