"""Rotas das integracoes (dentro do painel)."""

from django.urls import path

from integracoes import views

app_name = "integracoes"

urlpatterns = [
    path("gestao/integracoes/", views.IntegracoesView.as_view(), name="painel"),
    path(
        "gestao/integracoes/<str:provedor>/",
        views.ConfigurarIntegracaoView.as_view(),
        name="configurar",
    ),
    path(
        "gestao/integracoes/<str:provedor>/testar/",
        views.TestarIntegracaoView.as_view(),
        name="testar",
    ),
]
