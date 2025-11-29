from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('enviar-notificacao-atraso/', views.enviar_notificacao_atraso, name='enviar_notificacao_atraso'),
    path('enviar-mensagem-aniversario/', views.enviar_mensagem_aniversario, name='enviar_mensagem_aniversario'),
]
