"""Rotas da API v1 (documentacao em /api/docs/ e /api/redoc/)."""

from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from api import endpoints as ep
from api.recursos import router as router_recursos
from api.views import EstadoDaInstalacao, MinhaSessao

urlpatterns = [
    path("v1/auth/token/", ep.EntrarComSenha.as_view(), name="api-token"),
    path("v1/auth/refresh/", ep.RenovarToken.as_view(), name="api-refresh"),
    path("v1/estado/", EstadoDaInstalacao.as_view(), name="api-estado"),
    path("v1/estado-da-rede/", ep.EstadoDoTenant.as_view(), name="api-estado-rede"),
    path("v1/metricas-da-rede/", ep.MetricasDaRede.as_view(), name="api-metricas-rede"),
    path("v1/inadimplencia/", ep.InadimplenciaDaApi.as_view(), name="api-inadimplencia"),
    path("v1/relatorios/<str:tipo>/", ep.RelatorioDaApi.as_view(), name="api-relatorio"),
    path("v1/jobs/<int:pk>/", ep.JobDaApi.as_view(), name="api-job"),
    path("v1/lgpd/titulares/<int:pk>/<str:acao>/", ep.LgpdDaApi.as_view(), name="api-lgpd"),
    path("v1/playground/", ep.playground, name="api-playground"),
    path("v1/sessao/", MinhaSessao.as_view(), name="api-sessao"),
    path("v1/", include(router_recursos.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-redoc"),
]
