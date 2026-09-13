"""Rotas do painel da rede (montadas dentro de /gestao/)."""
from django.urls import path

from rede import views

app_name = "rede"

urlpatterns = [
    path("", views.RedePainelView.as_view(), name="painel"),
    path("unidades/", views.UnidadesView.as_view(), name="unidades"),
    path("unidades/nova/", views.UnidadeCriarView.as_view(), name="unidade_criar"),
    path("unidades/<int:pk>/", views.UnidadeEditarView.as_view(), name="unidade_editar"),
    path("unidades/<int:pk>/encerrar/", views.UnidadeEncerrarView.as_view(), name="unidade_encerrar"),
    path("unidades/template/", views.AplicarTemplateView.as_view(), name="unidade_template"),
    path("metas/", views.MetasView.as_view(), name="metas"),
    path("metas/nova/", views.MetaCriarView.as_view(), name="meta_criar"),
    path("repasses/", views.RepassesView.as_view(), name="repasses"),
    path("repasses/acao/", views.RepasseAcaoView.as_view(), name="repasse_acao"),
    path("repasses/<int:pk>/", views.RepasseDetalheView.as_view(), name="repasse_detalhe"),
    path("repasses/regras/", views.RegrasDeRepasseView.as_view(), name="regras"),
    path("repasses/regras/nova/", views.RegraCriarView.as_view(), name="regra_criar"),
    path("repasses/regras/<int:pk>/", views.RegraEditarView.as_view(), name="regra_editar"),
    path("governanca/", views.GovernancaView.as_view(), name="governanca"),
    path("comunicados/", views.ComunicadosView.as_view(), name="comunicados"),
    path("comunicados/novo/", views.ComunicadoCriarView.as_view(), name="comunicado_criar"),
    path("comunicados/<int:pk>/ler/", views.LerComunicadoView.as_view(), name="comunicado_ler"),
    path("aprovacoes/", views.AprovacoesView.as_view(), name="aprovacoes"),
    path("aprovacoes/<int:pk>/decidir/", views.DecidirAprovacaoView.as_view(), name="aprovacao_decidir"),
    path("catalogo/", views.CatalogoView.as_view(), name="catalogo"),
    path("transferencias/", views.TransferenciasView.as_view(), name="transferencias"),
    path("importar/", views.ImportarDaRedeView.as_view(), name="importar"),
    path("demonstrativo/<int:pk>.csv", views.RepasseCsvView.as_view(), name="repasse_csv"),
]
