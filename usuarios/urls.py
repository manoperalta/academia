from django.urls import path
from . import views

urlpatterns = [
    path('', views.usuario_list, name='usuario_list'),
    path('novo/', views.usuario_create, name='usuario_create'),
    path('editar/<int:pk>/', views.usuario_update, name='usuario_update'),
    path('excluir/<int:pk>/', views.usuario_delete, name='usuario_delete'),
]
