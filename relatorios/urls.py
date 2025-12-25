from django.urls import path
from . import views

urlpatterns = [
    path('', views.relatorio_geral, name='relatorio_geral'),
    path('financeiro/', views.relatorio_financeiro, name='relatorio_financeiro'),
    path('usuarios/', views.relatorio_usuarios, name='relatorio_usuarios'),
    path('extrato/', views.relatorio_extrato, name='relatorio_extrato'),
]
