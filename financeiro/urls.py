from django.urls import path
from . import views

urlpatterns = [
    path('pagamentos/', views.pagamento_list, name='pagamento_list'),
    path('pagamentos/novo/', views.pagamento_create, name='pagamento_create'),
    path('pagamentos/excluir/<int:pk>/', views.pagamento_delete, name='pagamento_delete'),
    path('pagamentos/checkout/<int:pk>/', views.realizar_checkout, name='realizar_checkout'),
    path('pagamentos/detalhe/<int:pk>/', views.pagamento_detalhe, name='pagamento_detalhe'),
    path('planos/', views.plano_list, name='plano_list'),
    path('planos/novo/', views.plano_create, name='plano_create'),
    path('planos/editar/<int:pk>/', views.plano_update, name='plano_update'),
    path('planos/excluir/<int:pk>/', views.plano_delete, name='plano_delete'),
    path('planos/comprar/<int:pk>/', views.comprar_plano, name='comprar_plano'),
    path('pagamentos/atualizar-status/<int:pk>/', views.atualizar_status_pagamento, name='atualizar_status_pagamento'),
]
