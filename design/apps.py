"""App do design system: tokens e componentes reutilizaveis do painel."""

from django.apps import AppConfig


class DesignConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "design"
    verbose_name = "Design system"
