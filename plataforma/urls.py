"""Rotas do painel da plataforma (/plataforma/) e do webhook do gateway."""
from django.urls import path

from plataforma import views

app_name = "plataforma"

urlpatterns = [
    path("", views.MetricasView.as_view(), name="metricas"),
    path("configuracao/", views.ConfiguracaoView.as_view(), name="config"),
    path("webhook/asaas/", views.WebhookAsaasView.as_view(), name="webhook_asaas"),
    # tenants
    path("clientes/", views.TenantsView.as_view(), name="tenants"),
    path("clientes/novo/", views.TenantCriarView.as_view(), name="tenant_novo"),
    path("clientes/<int:pk>/", views.TenantFichaView.as_view(), name="tenant_ficha"),
    path("clientes/<int:pk>/editar/", views.TenantEditarView.as_view(), name="tenant_editar"),
    path("clientes/<int:pk>/acao/<str:acao>/", views.TenantAcaoView.as_view(), name="tenant_acao"),
    path("clientes/<int:pk>/faturar/", views.FaturaEmitirView.as_view(), name="tenant_faturar"),
    path("clientes/<int:pk>/impersonar/", views.ImpersonarView.as_view(), name="impersonar"),
    # pacotes
    path("pacotes/", views.PacotesView.as_view(), name="pacotes"),
    path("pacotes/novo/", views.PacoteCriarView.as_view(), name="pacote_novo"),
    path("pacotes/<int:pk>/editar/", views.PacoteEditarView.as_view(), name="pacote_editar"),
    # cobranca
    path("faturas/", views.FaturasView.as_view(), name="faturas"),
    path("faturas/<int:pk>/baixar/", views.FaturaBaixarView.as_view(), name="fatura_baixar"),
    path("faturas/<int:pk>/cancelar/", views.FaturaCancelarView.as_view(), name="fatura_cancelar"),
    path("faturas/<int:pk>/cobrar/", views.FaturaEmitirCobrancaView.as_view(), name="fatura_cobrar"),
    path("faturas/<int:pk>/simular-pagamento/", views.FaturaSimularPagamentoView.as_view(),
         name="fatura_simular_pagamento"),
    path("regua/", views.ReguaView.as_view(), name="regua"),
    path("saude/", views.SaudeView.as_view(), name="saude"),
    path("backups/", views.BackupsView.as_view(), name="backups"),
    path("backups/acao/", views.BackupAcaoView.as_view(), name="backups_acao"),
    path("dominios/", views.DominiosView.as_view(), name="dominios"),
    path("dominios/<int:pk>/acao/", views.DominioAcaoView.as_view(), name="dominios_acao"),
    path("lgpd/", views.LgpdView.as_view(), name="lgpd"),
    path("webhooks/", views.WebhooksView.as_view(), name="webhooks"),
    path("relatorio/", views.RelatorioFinanceiroView.as_view(), name="relatorio"),
    path("relatorio.csv", views.RelatorioFinanceiroCsvView.as_view(), name="relatorio_csv"),
    path("sair-impersonacao/", views.SairImpersonacaoView.as_view(), name="sair_impersonacao"),
]
