from django.urls import path
from . import views

urlpatterns = [
    path('', views.painel_list, name='painel_list'),
    path('novo/', views.painel_create, name='painel_create'),
    path('editar/<int:pk>/', views.painel_update, name='painel_update'),
    path('excluir/<int:pk>/', views.painel_delete, name='painel_delete'),
]
