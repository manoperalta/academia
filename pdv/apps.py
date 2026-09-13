"""App do PDV: venda no balcao e estoque."""

from django.apps import AppConfig


class PdvConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pdv"
    verbose_name = "PDV e estoque"
