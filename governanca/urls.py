"""Rotas de governanca: entrar, 2FA, midia protegida, status e privacidade."""

from django.urls import path

from governanca import views

app_name = "governanca"

urlpatterns = [
    path("entrar/", views.LoginSeguroView.as_view(), name="entrar"),
    path("sair/", views.SairView.as_view(), name="sair"),
    path("2fa/", views.DoisFatoresView.as_view(), name="dois_fatores"),
    path("2fa/cadastrar/", views.Cadastrar2FAView.as_view(), name="dois_fatores_cadastrar"),
    path("2fa/codigos/", views.CodigosDeRecuperacaoView.as_view(), name="dois_fatores_codigos"),
    path("2fa/desativar/", views.Desativar2FAView.as_view(), name="dois_fatores_desativar"),
    path("midia/<path:caminho>", views.MidiaView.as_view(), name="midia"),
    path("status/", views.StatusView.as_view(), name="status"),
    path("privacidade/", views.PrivacidadeView.as_view(), name="privacidade"),
]
