"""Rotas da cobranca recorrente."""

from django.urls import path

from cobranca import views

app_name = "cobranca"

urlpatterns = [
    path("gestao/cobranca/", views.PainelDeCobrancaView.as_view(), name="painel"),
    path("gestao/cobranca/cobrancas/", views.CobrancasView.as_view(), name="lista"),
    path("gestao/cobranca/gerar/", views.GerarCobrancasView.as_view(), name="gerar"),
    path("gestao/cobranca/autorizacoes/", views.AutorizacoesView.as_view(), name="autorizacoes"),
    path("gestao/cobranca/autorizar/", views.AutorizarDebitoView.as_view(), name="autorizar"),
    path(
        "gestao/cobranca/autorizacoes/<int:pk>/ativar/",
        views.AtivarAutorizacaoView.as_view(),
        name="ativar_autorizacao",
    ),
    path(
        "gestao/cobranca/autorizacoes/<int:pk>/cancelar/",
        views.CancelarAutorizacaoView.as_view(),
        name="cancelar_autorizacao",
    ),
    path(
        "gestao/cobranca/cobrancas/<int:pk>/enviar/",
        views.EnviarCobrancaView.as_view(),
        name="enviar",
    ),
    path(
        "gestao/cobranca/cobrancas/<int:pk>/lembrete/",
        views.LembreteView.as_view(),
        name="lembrete",
    ),
    path(
        "gestao/cobranca/cobrancas/<int:pk>/cancelar/",
        views.CancelarCobrancaView.as_view(),
        name="cancelar_cobranca",
    ),
    path("gestao/cobranca/retorno/", views.RetornoEmLoteView.as_view(), name="retorno_em_lote"),
    path("api/cobranca/retorno/", views.WebhookDeCobrancaView.as_view(), name="webhook"),
]
