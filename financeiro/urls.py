from django.urls import path
from . import views

urlpatterns = [
    path('pagamentos/', views.pagamento_list, name='pagamento_list'),
    path('pagamentos/novo/', views.pagamento_create, name='pagamento_create'),
    path('pagamentos/excluir/<int:pk>/', views.pagamento_delete, name='pagamento_delete'),
    path('planos/', views.plano_list, name='plano_list'),
]
