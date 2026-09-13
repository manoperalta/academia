"""Rotas do painel de gamificacao."""

from __future__ import annotations

from django.urls import path

from gamificacao import views

app_name = "gamificacao"

urlpatterns = [
    path("", views.RegrasDePontosView.as_view(), name="regras"),
    path("nova/", views.RegraDePontosNovaView.as_view(), name="regra_nova"),
    path("<int:pk>/editar/", views.RegraDePontosEditarView.as_view(), name="regra_editar"),
    path("conquistas/", views.ConquistasView.as_view(), name="conquistas"),
    path("conquistas/nova/", views.ConquistaNovaView.as_view(), name="conquista_nova"),
    path(
        "conquistas/<int:pk>/editar/", views.ConquistaEditarView.as_view(), name="conquista_editar"
    ),
    path("ranking/", views.RankingView.as_view(), name="ranking"),
]
