"""Rotas da midia: telas do painel, API do envio em partes e entrega assinada."""

from django.urls import path

from midia import views

app_name = "midia"

urlpatterns = [
    path("gestao/midia/", views.ListaDeMidiaView.as_view(), name="lista"),
    path("gestao/midia/enviar/", views.EnvioDeMidiaView.as_view(), name="enviar"),
    path("gestao/midia/arquivo/<int:pk>/", views.PlayerDaMidiaView.as_view(), name="player"),
    path("midia/api/iniciar/", views.IniciarEnvioView.as_view(), name="api_iniciar"),
    path("midia/api/<int:pk>/parte/", views.ReceberParteView.as_view(), name="api_parte"),
    path("midia/api/<int:pk>/concluir/", views.ConcluirEnvioView.as_view(), name="api_concluir"),
    path("midia/api/<int:pk>/status/", views.StatusDoEnvioView.as_view(), name="api_status"),
    path("midia/<int:pk>/entrega/", views.EntregaDaMidiaView.as_view(), name="entrega"),
    path("aluno/aula/<int:pk>/assistir/", views.MidiaDoAlunoView.as_view(), name="aluno_assistir"),
]
