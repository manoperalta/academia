"""App fiscal: nota de servico (NFS-e) da mensalidade."""

from django.apps import AppConfig


class FiscalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fiscal"
    verbose_name = "Fiscal (NFS-e)"
