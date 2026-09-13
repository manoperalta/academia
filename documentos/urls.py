"""Rotas dos documentos: painel (por rede) e area do aluno (a propria carteirinha)."""

from django.urls import path

from documentos import views

app_name = "documentos"

urlpatterns = [
    path(
        "gestao/documentos/matricula/<int:pk>/",
        views.ComprovanteDeMatriculaView.as_view(),
        name="comprovante_de_matricula",
    ),
    path(
        "gestao/documentos/carteirinha/<int:pk>/",
        views.CarteirinhaDoAlunoView.as_view(),
        name="carteirinha",
    ),
    path(
        "gestao/documentos/contrato/<int:pk>/",
        views.ContratoDeAdesaoView.as_view(),
        name="contrato",
    ),
    path(
        "gestao/documentos/recibo/<int:pk>/", views.ReciboDePagamentoView.as_view(), name="recibo"
    ),
    path(
        "gestao/documentos/repasse/<int:pk>/",
        views.DemonstrativoDeRepasseView.as_view(),
        name="demonstrativo_de_repasse",
    ),
    path(
        "gestao/documentos/comissao/<int:pk>/",
        views.ExtratoDeComissaoView.as_view(),
        name="extrato_de_comissao",
    ),
    path("aluno/carteirinha/", views.MinhaCarteirinhaView.as_view(), name="minha_carteirinha"),
    path("gestao/documentos/assinatura/", views.EnvelopesView.as_view(), name="envelopes"),
    path(
        "gestao/documentos/assinatura/criar/",
        views.CriarEnvelopeView.as_view(),
        name="criar_envelope",
    ),
    path(
        "gestao/documentos/assinatura/<int:pk>/",
        views.EnvelopeDetalheView.as_view(),
        name="envelope",
    ),
    path(
        "gestao/documentos/assinatura/signatario/<int:pk>/assinar/",
        views.AssinarEnvelopeView.as_view(),
        name="assinar",
    ),
    path(
        "gestao/documentos/assinatura/signatario/<int:pk>/recusar/",
        views.RecusarEnvelopeView.as_view(),
        name="recusar",
    ),
    path(
        "gestao/documentos/assinatura/<int:pk>/termo/",
        views.TermoDeAssinaturasView.as_view(),
        name="termo_de_assinaturas",
    ),
    path(
        "gestao/documentos/assinatura/<int:pk>/verificar/",
        views.VerificarEnvelopeView.as_view(),
        name="verificar",
    ),
]
