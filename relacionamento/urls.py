"""Rotas do CRM e da retencao."""

from django.urls import path

from relacionamento import views

app_name = "relacionamento"

urlpatterns = [
    path("gestao/crm/", views.FunilView.as_view(), name="funil"),
    path("gestao/crm/leads/", views.ListaDeLeadsView.as_view(), name="leads"),
    path("gestao/crm/leads/<int:pk>/", views.LeadDetalheView.as_view(), name="lead"),
    path(
        "gestao/crm/leads/<int:pk>/interacao/",
        views.RegistrarInteracaoView.as_view(),
        name="interacao",
    ),
    path(
        "gestao/crm/leads/<int:pk>/converter/", views.ConverterLeadView.as_view(), name="converter"
    ),
    path("gestao/crm/leads/<int:pk>/perder/", views.PerderLeadView.as_view(), name="perder"),
    path("gestao/retencao/", views.FilaDeRetencaoView.as_view(), name="retencao"),
    path("gestao/retencao/atualizar/", views.AtualizarRiscoView.as_view(), name="atualizar_risco"),
    path("gestao/retencao/<int:pk>/", views.DetalheDoRiscoView.as_view(), name="risco"),
    path("gestao/retencao/<int:pk>/desfecho/", views.DesfechoView.as_view(), name="desfecho"),
]
