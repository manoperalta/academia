"""Rotas do site publico (raiz do dominio)."""

from django.urls import path

from vitrine import views

app_name = "vitrine"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("planos/", views.PlanosView.as_view(), name="planos"),
    path("cadastro/", views.CadastroView.as_view(), name="cadastro"),
    path("cadastro/concluido/", views.CadastroConcluidoView.as_view(), name="cadastro_concluido"),
    path("ajuda/", views.AjudaView.as_view(), name="ajuda"),
    path("contato/", views.ContatoView.as_view(), name="contato"),
    path("api/slug/", views.VerificarSlugView.as_view(), name="verificar_slug"),
    path("api/cnpj/", views.VerificarCnpjView.as_view(), name="verificar_cnpj"),
]
