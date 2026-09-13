"""Rotas do painel de comissoes."""

from __future__ import annotations

from django.urls import path

from remuneracao import views

app_name = "remuneracao"

urlpatterns = [
    path("", views.RegrasView.as_view(), name="regras"),
    path("nova/", views.RegraNovaView.as_view(), name="regra_nova"),
    path("<int:pk>/editar/", views.RegraEditarView.as_view(), name="regra_editar"),
    path("apuracoes/", views.ApuracoesView.as_view(), name="apuracoes"),
    path("apuracoes/<int:pk>/", views.ApuracaoDetalheView.as_view(), name="apuracao_detalhe"),
    path("apuracoes/<int:pk>/baixar/", views.BaixarComissaoView.as_view(), name="apuracao_baixar"),
    path("apurar/", views.ApurarCompetenciaView.as_view(), name="apurar"),
    path("extrato/", views.ExtratoDoProfessorView.as_view(), name="extrato"),
]
