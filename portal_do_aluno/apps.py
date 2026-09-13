"""App do portal do aluno: agenda, pagamentos, ficha de saude e perfil."""

from django.apps import AppConfig


class PortalDoAlunoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal_do_aluno"
    verbose_name = "Portal do aluno"
