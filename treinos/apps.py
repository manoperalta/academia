"""App de treinos: prescricao, execucao e avaliacao fisica."""

from django.apps import AppConfig


class TreinosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "treinos"
    verbose_name = "Treinos e avaliacoes"
