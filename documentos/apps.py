"""App dos documentos de negocio (PDF)."""

from django.apps import AppConfig


class DocumentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "documentos"
    verbose_name = "Documentos de negocio"
