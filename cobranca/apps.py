"""App de cobranca recorrente: autorizacao de debito, cobranca do mes e retorno."""

from django.apps import AppConfig


class CobrancaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cobranca"
    verbose_name = "Cobranca recorrente"
