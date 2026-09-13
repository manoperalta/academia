"""Rotas do controle de acesso, da catraca e dos parceiros."""

from django.urls import path

from acesso import views

app_name = "acesso"

urlpatterns = [
    path("gestao/acesso/", views.PainelDeAcessoView.as_view(), name="painel"),
    path("gestao/acesso/registros/", views.RegistrosDeAcessoView.as_view(), name="registros"),
    path("gestao/acesso/liberar/", views.LiberarManualView.as_view(), name="liberar"),
    path("gestao/acesso/credenciais/", views.CredenciaisView.as_view(), name="credenciais"),
    path(
        "gestao/acesso/credenciais/emitir/",
        views.EmitirCredencialView.as_view(),
        name="emitir_credencial",
    ),
    path(
        "gestao/acesso/credenciais/<int:pk>/cancelar/",
        views.CancelarCredencialView.as_view(),
        name="cancelar_credencial",
    ),
    path(
        "gestao/acesso/dispositivos/",
        views.CriarDispositivoView.as_view(),
        name="criar_dispositivo",
    ),
    path("gestao/acesso/parceiros/", views.ParceirosView.as_view(), name="parceiros"),
    path(
        "gestao/acesso/parceiros/plano/",
        views.CriarPlanoDeParceiroView.as_view(),
        name="criar_plano",
    ),
    path(
        "gestao/acesso/parceiros/importar/",
        views.ImportarExtratoView.as_view(),
        name="importar_extrato",
    ),
    path(
        "gestao/acesso/parceiros/extrato/<int:pk>/",
        views.ExtratoDetalheView.as_view(),
        name="extrato",
    ),
    path(
        "gestao/acesso/parceiros/extrato/<int:pk>/conciliar/",
        views.ConciliarExtratoView.as_view(),
        name="conciliar",
    ),
    path("api/acesso/liberar/", views.IntegracaoDaCatracaView.as_view(), name="integracao"),
]
