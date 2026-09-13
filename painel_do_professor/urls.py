"""Rotas do painel do professor."""

from django.urls import path

from painel_do_professor import views

app_name = "professor"

urlpatterns = [
    path("professor/", views.MinhaAgendaView.as_view(), name="agenda"),
    path(
        "professor/agenda/",
        views.MinhasDisponibilidadesView.as_view(),
        name="disponibilidades",
    ),
    path("professor/agenda/abrir/", views.AbrirAgendaView.as_view(), name="abrir_agenda"),
    path(
        "professor/agenda/<int:pk>/editar/",
        views.EditarDisponibilidadeView.as_view(),
        name="editar_disponibilidade",
    ),
    path(
        "professor/agenda/<int:pk>/encerrar/",
        views.EncerrarDisponibilidadeView.as_view(),
        name="encerrar_disponibilidade",
    ),
    path(
        "professor/agenda/republicar/",
        views.AtualizarAgendaView.as_view(),
        name="atualizar_agenda",
    ),
    path("professor/turma/<int:pk>/", views.MinhaTurmaView.as_view(), name="turma"),
    path("professor/turma/<int:pk>/chamada/", views.ChamadaView.as_view(), name="chamada"),
    path("professor/turma/<int:pk>/ocorrencia/", views.OcorrenciaView.as_view(), name="ocorrencia"),
    path(
        "professor/turma/<int:pk>/substituicao/",
        views.SubstituicaoView.as_view(),
        name="substituicao",
    ),
    path("professor/treinos/", views.MeusTreinosView.as_view(), name="treinos"),
    path("professor/treinos/novo/", views.PrescreverTreinoView.as_view(), name="prescrever"),
    path("professor/treinos/<int:pk>/", views.TreinoDoProfessorView.as_view(), name="treino"),
    path(
        "professor/treinos/<int:pk>/exercicio/",
        views.AdicionarExercicioView.as_view(),
        name="adicionar_exercicio",
    ),
    path(
        "professor/treinos/<int:pk>/duplicar/",
        views.DuplicarTreinoView.as_view(),
        name="duplicar_treino",
    ),
    path("professor/alunos/", views.MeusAlunosView.as_view(), name="alunos"),
    path("professor/alunos/<int:pk>/", views.AlunoDoProfessorView.as_view(), name="aluno"),
    path("professor/avaliacoes/", views.MinhasAvaliacoesView.as_view(), name="avaliacoes"),
    path(
        "professor/avaliacoes/registrar/",
        views.RegistrarAvaliacaoView.as_view(),
        name="registrar_avaliacao",
    ),
    path("professor/comissoes/", views.MinhasComissoesView.as_view(), name="comissoes"),
]
