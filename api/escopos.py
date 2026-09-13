"""Escopos de token (PRD secao 20.3).

Formato: ``<recurso>:<operacao>``. Um token recebe uma lista de escopos e so
alcanca o que ela permitir. ``*`` no fim concede tudo do recurso.
"""

from __future__ import annotations

ESCOPOS = {
    # plataforma
    "plataforma:read": "Ver redes, pacotes, faturas e metricas da plataforma",
    "plataforma:write": "Administrar redes, pacotes, assinaturas e faturas",
    # rede e unidades
    "rede:read": "Ver dados da rede, governanca e metas",
    "rede:write": "Editar dados da rede, governanca e metas",
    "unidades:read": "Ver unidades",
    "unidades:write": "Criar e editar unidades",
    # operacao
    "alunos:read": "Ver alunos, matriculas e historico",
    "alunos:write": "Criar e editar alunos e matriculas",
    "saude:read": "Ver ficha de saude e avaliacoes fisicas (dado sensivel)",
    "saude:write": "Editar ficha de saude e avaliacoes fisicas",
    "professores:read": "Ver professores e vinculos",
    "professores:write": "Criar e editar professores",
    "equipe:read": "Ver usuarios internos e papeis",
    "equipe:write": "Convidar, alterar papeis e revogar acessos",
    "aulas:read": "Ver aulas, treinos e midia",
    "aulas:write": "Criar e editar aulas, treinos e enviar midia",
    "agenda:read": "Ver turmas, paineis, agendamentos e presenca",
    "agenda:write": "Criar e editar turmas, paineis e agendamentos",
    "financeiro:read": "Ver planos, contratos, cobrancas e pagamentos",
    "financeiro:write": "Emitir e baixar cobrancas, aplicar desconto e renegociar",
    "repasses:read": "Ver repasses e royalties",
    "repasses:write": "Calcular e emitir repasses",
    "comunicacao:read": "Ver templates e campanhas",
    "comunicacao:write": "Criar e disparar campanhas e mensagens",
    "relatorios:read": "Gerar e baixar relatorios",
    "auditoria:read": "Ler a trilha de auditoria",
    "webhooks:write": "Cadastrar webhooks de saida",
}

#: Escopos que exigem cuidado extra (dado sensivel / acao financeira).
ESCOPOS_SENSIVEIS = frozenset(
    {
        "plataforma:write",
        "saude:read",
        "saude:write",
        "financeiro:write",
        "repasses:write",
        "comunicacao:write",
        "equipe:write",
    }
)


def tem_escopo(escopos_do_token, exigido: str) -> bool:
    """Verifica se o token possui o escopo pedido (aceita curinga ``*``)."""
    if not exigido:
        return True
    escopos_do_token = set(escopos_do_token or [])
    if "*" in escopos_do_token or exigido in escopos_do_token:
        return True
    recurso = exigido.split(":", 1)[0]
    return f"{recurso}:*" in escopos_do_token
