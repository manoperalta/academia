from django.urls import path
from . import views

urlpatterns = [
    path('', views.relatorio_geral, name='relatorio_geral'),
]
