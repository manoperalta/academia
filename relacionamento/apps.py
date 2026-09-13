"""App de relacionamento: captacao (CRM) e retencao de alunos."""

from django.apps import AppConfig


class RelacionamentoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "relacionamento"
    verbose_name = "CRM e retencao"
