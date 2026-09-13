"""Rota da busca global."""

from django.urls import path

from busca import views

app_name = "busca"

urlpatterns = [
    path("gestao/busca/", views.BuscaView.as_view(), name="resultados"),
]
