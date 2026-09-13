"""App de gamificacao (pontos e conquistas)."""

from django.apps import AppConfig


class GamificacaoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gamificacao"
    verbose_name = "Gamificacao"
