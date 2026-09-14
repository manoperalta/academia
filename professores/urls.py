from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProfessorListView.as_view(), name="professor_list"),
    path("novo/", views.ProfessorCreateView.as_view(), name="professor_create"),
    path("editar/<int:pk>/", views.ProfessorUpdateView.as_view(), name="professor_update"),
    path("excluir/<int:pk>/", views.ProfessorDeleteView.as_view(), name="professor_delete"),
    path(
        "completar-perfil/",
        views.complete_profile_professor,
        name="complete_profile_professor",
    ),
]
