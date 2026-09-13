"""Servicos de schema: OpenAPI 3 para documentacao viva (RNF-037)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema, extend_schema_view

from api.viewsets import (
    AlunoViewSet,
    ApiTokenViewSet,
    AuditoriaViewSet,
    AulaViewSet,
    PagamentoViewSet,
    PlanoViewSet,
    ProfessorViewSet,
    RedeViewSet,
    UnidadeViewSet,
    VinculoUsuarioViewSet,
)

ETIQUETAS = {
    "rede": "Rede (tenant)",
    "unidades": "Unidades",
    "equipe": "Equipe e permissoes",
    "alunos": "Alunos",
    "professores": "Professores",
    "aulas": "Aulas e treinos",
    "financeiro": "Financeiro",
    "auditoria": "Auditoria",
    "apitoken": "Tokens de API",
}

#: Aplica resumo/etiqueta em todos os ViewSets sem repetir decorador em cada um.
RedeViewSet = extend_schema_view(
    list=extend_schema(tags=["Rede (tenant)"]),
    create=extend_schema(tags=["Rede (tenant)"]),
)(RedeViewSet)
UnidadeViewSet = extend_schema_view(tags=["Unidades"])(UnidadeViewSet)
AlunoViewSet = extend_schema_view(tags=["Alunos"])(AlunoViewSet)
ProfessorViewSet = extend_schema_view(tags=["Professores"])(ProfessorViewSet)
AulaViewSet = extend_schema_view(tags=["Aulas e treinos"])(AulaViewSet)
PlanoViewSet = extend_schema_view(tags=["Financeiro"])(PlanoViewSet)
PagamentoViewSet = extend_schema_view(tags=["Financeiro"])(PagamentoViewSet)
VinculoUsuarioViewSet = extend_schema_view(tags=["Equipe e permissoes"])(VinculoUsuarioViewSet)
ApiTokenViewSet = extend_schema_view(tags=["Tokens de API"])(ApiTokenViewSet)
AuditoriaViewSet = extend_schema_view(tags=["Auditoria"])(AuditoriaViewSet)
