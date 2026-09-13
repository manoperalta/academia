"""Rotas da API v1 (documentacao em /api/docs/ e /api/redoc/)."""

from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from api.schema import (
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
from api.views import EstadoDaInstalacao, MinhaSessao

router = DefaultRouter()
router.register("redes", RedeViewSet, basename="rede")
router.register("unidades", UnidadeViewSet, basename="unidade")
router.register("equipe", VinculoUsuarioViewSet, basename="vinculo")
router.register("alunos", AlunoViewSet, basename="aluno")
router.register("professores", ProfessorViewSet, basename="professor")
router.register("aulas", AulaViewSet, basename="aula")
router.register("planos", PlanoViewSet, basename="plano")
router.register("pagamentos", PagamentoViewSet, basename="pagamento")
router.register("tokens", ApiTokenViewSet, basename="apitoken")
router.register("auditoria", AuditoriaViewSet, basename="auditoria")

urlpatterns = [
    path("v1/estado/", EstadoDaInstalacao.as_view(), name="api-estado"),
    path("v1/sessao/", MinhaSessao.as_view(), name="api-sessao"),
    path("v1/", include(router.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
]
