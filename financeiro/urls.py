from django.urls import path
from . import views

urlpatterns = [
    path('pagamentos/', views.pagamento_list, name='pagamento_list'),
    path('pagamentos/novo/', views.pagamento_create, name='pagamento_create'),
    path('pagamentos/excluir/<int:pk>/', views.pagamento_delete, name='pagamento_delete'),
    path('pagamentos/checkout/<int:pk>/', views.realizar_checkout, name='realizar_checkout'),
    path('pagamentos/detalhe/<int:pk>/', views.pagamento_detalhe, name='pagamento_detalhe'),
    path('planos/', views.plano_list, name='plano_list'),
]
