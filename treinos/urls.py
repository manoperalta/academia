"""Rotas do app de treinos (a area do aluno usa estas telas)."""

from django.urls import path

from treinos import views

app_name = "treinos"

urlpatterns = [
    path("aluno/treinos/", views.MeusTreinosDoAlunoView.as_view(), name="meus_treinos"),
    path("aluno/treinos/<int:pk>/", views.TreinoDoAlunoView.as_view(), name="meu_treino"),
    path(
        "aluno/treinos/exercicio/<int:pk>/execucao/",
        views.RegistrarExecucaoView.as_view(),
        name="registrar_execucao",
    ),
    path("aluno/evolucao/", views.MinhaEvolucaoView.as_view(), name="minha_evolucao"),
]
