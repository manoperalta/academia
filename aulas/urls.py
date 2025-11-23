from django.urls import path
from . import views

urlpatterns = [
    path('', views.aulas_list, name='aulas_list'),
    path('nova/', views.aulas_create, name='aulas_create'),
    path('editar/<int:pk>/', views.aulas_update, name='aulas_update'),
    path('excluir/<int:pk>/', views.aulas_delete, name='aulas_delete'),
]
