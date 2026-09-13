"""App do painel do professor: agenda, turmas, prescricao, alunos e comissoes."""

from django.apps import AppConfig


class PainelDoProfessorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "painel_do_professor"
    verbose_name = "Painel do professor"
