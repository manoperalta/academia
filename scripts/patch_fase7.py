#!/usr/bin/env python3
"""Fase 7: monta a API v1 (30 recursos), os endpoints novos e os modelos de integracao."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def patch_models() -> None:
    caminho = RAIZ / "api" / "models.py"
    texto = caminho.read_text(encoding="utf-8")
    if "modelos_de_integracao" in texto:
        print("api/models.py: integracao ja importada")
        return
    texto = texto.rstrip("\n") + "\n\n\n# Fase 7: webhooks de saida e tarefas assincronas\nfrom api.modelos_de_integracao import *  # noqa: F401,F403,E402\n"
    if "modelos_de_integracao" not in texto:
        raise SystemExit("ERRO: import de integracao nao entrou")
    caminho.write_text(texto, encoding="utf-8")
    print("api/models.py: modelos de integracao registrados")


def patch_urls() -> None:
    caminho = RAIZ / "api" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "api.recursos" in texto:
        print("api/urls.py: ja montado")
        return
    inicio = texto.index("from api.schema import (")
    fim = texto.index(")", texto.index("AlunoViewSet", inicio)) + 1
    texto = texto[:inicio] + texto[fim:].lstrip("\n")
    corte = texto.index("router = DefaultRouter()")
    cabeca = texto[:corte]
    novo = '''from api import endpoints as ep
from api.recursos import router as router_recursos
from api.views import MinhaSessao

urlpatterns = [
    path("v1/auth/token/", ep.EntrarComSenha.as_view(), name="api-token"),
    path("v1/auth/refresh/", ep.RenovarToken.as_view(), name="api-refresh"),
    path("v1/estado/", ep.EstadoDoTenant.as_view(), name="api-estado"),
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
'''
    texto = cabeca + novo
    for exigido in ("api.recursos", "auth/token", "playground"):
        if exigido not in texto:
            raise SystemExit(f"ERRO: {exigido} nao entrou em api/urls.py")
    caminho.write_text(texto, encoding="utf-8")
    print("api/urls.py: 30 recursos + auth + estado + relatorios + playground")


def patch_settings() -> None:
    caminho = RAIZ / "app" / "settings_env" / "base.py"
    texto = caminho.read_text(encoding="utf-8")
    if "TAREFAS_DIR" in texto:
        print("settings: TAREFAS_DIR ja definido")
        return
    texto = texto.rstrip("\n") + '''

# ------------------------------------------------ API v1 (fase 7)
API_JWT_SECRET = os.environ.get("API_JWT_SECRET", "")
API_JWT_VALIDADE = 3600
TAREFAS_DIR = os.environ.get("TAREFAS_DIR", BASE_DIR / "tarefas")
'''
    if "API_JWT_SECRET" not in texto:
        raise SystemExit("ERRO: settings da API nao entraram")
    caminho.write_text(texto, encoding="utf-8")
    print("settings: API_JWT_SECRET e TAREFAS_DIR")


if __name__ == "__main__":
    patch_models()
    patch_urls()
    patch_settings()
    print("patch fase 7 concluido")
