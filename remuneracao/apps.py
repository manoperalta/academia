"""App de remuneracao variavel (comissoes de professor)."""

from django.apps import AppConfig


class RemuneracaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "remuneracao"
    verbose_name = "Remuneracao e comissoes"
