"""Rotas publicas do aluno (PWA)."""

from __future__ import annotations

from django.urls import path

from area_do_aluno import views

app_name = "aluno"

urlpatterns = [
    path("", views.InicioDoAlunoView.as_view(), name="inicio"),
    path("checkin/", views.CheckinView.as_view(), name="checkin"),
    path("pontos/", views.PontosView.as_view(), name="pontos"),
    path("pesquisa/<int:pk>/", views.PesquisaDoAlunoView.as_view(), name="pesquisa"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("icone-<int:tamanho>.png", views.icone, name="icone"),
    path("offline/", views.offline, name="offline"),
]
