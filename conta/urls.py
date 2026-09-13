"""Rotas de conta e suporte."""

from django.urls import path

from conta import views

app_name = "conta"

urlpatterns = [
    path("conta/perfil/", views.MeuPerfilView.as_view(), name="perfil"),
    path("conta/senha/", views.AlterarSenhaView.as_view(), name="senha"),
    path("conta/senha/redefinir/", views.RecuperarSenhaView.as_view(), name="senha_redefinir"),
    path(
        "conta/senha/redefinir/enviado/",
        views.SenhaRedefinidaView.as_view(),
        name="senha_redefinida",
    ),
    path(
        "conta/senha/redefinir/<uidb64>/<token>/",
        views.ConfirmarNovaSenhaView.as_view(),
        name="senha_confirmar",
    ),
    path("conta/senha/redefinida/", views.SenhaAlteradaView.as_view(), name="senha_alterada"),
    path("conta/sessoes/", views.SessoesAtivasView.as_view(), name="sessoes"),
    path("conta/suporte/", views.MeusChamadosView.as_view(), name="chamados"),
    path("conta/suporte/<int:pk>/", views.ChamadoView.as_view(), name="chamado"),
    path("gestao/suporte/", views.FilaDoSuporteView.as_view(), name="fila_suporte"),
    path(
        "gestao/suporte/<int:pk>/responder/",
        views.ResponderChamadoView.as_view(),
        name="responder_chamado",
    ),
]
