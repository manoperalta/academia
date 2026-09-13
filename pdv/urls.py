"""Rotas do PDV."""

from django.urls import path

from pdv import views

app_name = "pdv"

urlpatterns = [
    path("gestao/pdv/", views.PainelDoPdvView.as_view(), name="painel"),
    path("gestao/pdv/produtos/", views.ProdutosView.as_view(), name="produtos"),
    path("gestao/pdv/produtos/salvar/", views.SalvarProdutoView.as_view(), name="salvar_produto"),
    path(
        "gestao/pdv/produtos/<int:pk>/estoque/",
        views.MovimentarEstoqueView.as_view(),
        name="movimentar",
    ),
    path("gestao/pdv/balcao/", views.BalcaoView.as_view(), name="balcao"),
    path("gestao/pdv/balcao/item/", views.AdicionarItemView.as_view(), name="adicionar_item"),
    path(
        "gestao/pdv/balcao/item/<int:pk>/remover/",
        views.RemoverItemView.as_view(),
        name="remover_item",
    ),
    path("gestao/pdv/balcao/<int:pk>/desconto/", views.DescontoView.as_view(), name="desconto"),
    path(
        "gestao/pdv/balcao/<int:pk>/finalizar/",
        views.FinalizarVendaView.as_view(),
        name="finalizar",
    ),
    path("gestao/pdv/vendas/", views.VendasView.as_view(), name="vendas"),
    path("gestao/pdv/vendas/<int:pk>/", views.VendaDetalheView.as_view(), name="venda"),
    path(
        "gestao/pdv/vendas/<int:pk>/cancelar/",
        views.CancelarVendaView.as_view(),
        name="cancelar_venda",
    ),
    path("gestao/pdv/movimentos/", views.MovimentosView.as_view(), name="movimentos"),
]
