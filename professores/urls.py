from django.urls import path
from . import views

urlpatterns = [
    path('', views.professor_list, name='professor_list'),
    path('novo/', views.professor_create, name='professor_create'),
    path('editar/<int:pk>/', views.professor_update, name='professor_update'),
    path('excluir/<int:pk>/', views.professor_delete, name='professor_delete'),
    path('completar-perfil/', views.complete_profile_professor, name='complete_profile_professor'),
]
