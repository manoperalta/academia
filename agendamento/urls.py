from django.urls import path
from . import views

urlpatterns = [
    # Rotas Aluno
    path('agenda/', views.agenda_list, name='agenda_list'),
    path('agendar/<int:painel_id>/', views.realizar_agendamento, name='realizar_agendamento'),
    path('meus-agendamentos/', views.meus_agendamentos, name='meus_agendamentos'),
    path('cancelar/<int:agendamento_id>/', views.cancelar_agendamento, name='cancelar_agendamento'),
]
