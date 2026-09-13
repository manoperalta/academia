"""App de midia: envio em partes, processamento e entrega assinada."""

from django.apps import AppConfig


class MidiaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "midia"
    verbose_name = "Midia"
