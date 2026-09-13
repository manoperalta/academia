"""Rota da vitrine do design system."""

from django.urls import path

from design import views

app_name = "design"

urlpatterns = [
    path("gestao/design/", views.VitrineView.as_view(), name="vitrine"),
]
