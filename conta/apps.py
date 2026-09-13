"""App de conta: perfil, senha, sessoes ativas e suporte."""

from django.apps import AppConfig


class ContaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "conta"
    verbose_name = "Conta e suporte"
