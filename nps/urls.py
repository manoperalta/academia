"""Rotas de NPS."""

from __future__ import annotations

from django.urls import path

from nps import views

app_name = "nps"

urlpatterns = [
    path("", views.PesquisasView.as_view(), name="pesquisas"),
    path("nova/", views.PesquisaNovaView.as_view(), name="pesquisa_nova"),
    path("<int:pk>/editar/", views.PesquisaEditarView.as_view(), name="pesquisa_editar"),
    path("painel/", views.PainelDoNpsView.as_view(), name="painel"),
    path("respostas/<int:pk>/tratar/", views.TratarDetratorView.as_view(), name="tratar"),
]
