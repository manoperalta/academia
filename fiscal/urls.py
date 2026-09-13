"""Rotas fiscais."""

from django.urls import path

from fiscal import views

app_name = "fiscal"

urlpatterns = [
    path("gestao/fiscal/", views.PainelFiscalView.as_view(), name="painel"),
    path(
        "gestao/fiscal/configuracao/", views.SalvarConfiguracaoView.as_view(), name="configuracao"
    ),
    path("gestao/fiscal/notas/", views.NotasFiscaisView.as_view(), name="notas"),
    path("gestao/fiscal/notas/<int:pk>/", views.NotaDetalheView.as_view(), name="nota"),
    path("gestao/fiscal/notas/<int:pk>/pdf/", views.BaixarNotaView.as_view(), name="pdf"),
    path(
        "gestao/fiscal/notas/<int:pk>/cancelar/", views.CancelarNotaView.as_view(), name="cancelar"
    ),
    path("gestao/fiscal/emitir/", views.EmitirNotaAvulsaView.as_view(), name="emitir"),
    path("gestao/fiscal/lote/", views.EmitirLoteView.as_view(), name="lote"),
]
