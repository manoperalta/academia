from django.urls import path
from . import views

urlpatterns = [
    # Rotas Professor
    path('paineis/', views.painel_list, name='painel_list'),
    path('paineis/novo/', views.painel_create, name='painel_create'),
    path('paineis/editar/<int:pk>/', views.painel_update, name='painel_update'),
    
    # Rotas Aluno
    path('agenda/', views.agenda_list, name='agenda_list'),
    path('agendar/<int:painel_id>/', views.realizar_agendamento, name='realizar_agendamento'),
    path('meus-agendamentos/', views.meus_agendamentos, name='meus_agendamentos'),
    path('cancelar/<int:agendamento_id>/', views.cancelar_agendamento, name='cancelar_agendamento'),
]
