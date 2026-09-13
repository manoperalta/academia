"""Rotas do portal do aluno."""

from django.urls import path

from portal_do_aluno import views

app_name = "portal"

urlpatterns = [
    path("aluno/agenda/", views.AgendaDoAlunoView.as_view(), name="agenda"),
    path("aluno/agenda/turma/<int:pk>/agendar/", views.AgendarView.as_view(), name="agendar"),
    path("aluno/agenda/turma/<int:pk>/espera/", views.ListaDeEsperaView.as_view(), name="espera"),
    path(
        "aluno/agenda/<int:pk>/cancelar/",
        views.CancelarAgendamentoView.as_view(),
        name="cancelar_agendamento",
    ),
    path("aluno/pagamentos/", views.MeusPagamentosView.as_view(), name="pagamentos"),
    path("aluno/ficha/", views.MinhaFichaView.as_view(), name="ficha"),
    path("aluno/perfil/", views.PerfilDoAlunoView.as_view(), name="perfil"),
    path("aluno/meus-dados/", views.MeusDadosView.as_view(), name="meus_dados"),
]
