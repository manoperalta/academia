"""App de pesquisas e NPS."""

from django.apps import AppConfig


class NpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nps"
    verbose_name = "Pesquisas e NPS"
