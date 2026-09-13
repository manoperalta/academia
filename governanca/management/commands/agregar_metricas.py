"""Persiste as metricas do cache e mostra os alertas (RNF-008)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.servicos import agregar_metricas, alertas_pendentes


class Command(BaseCommand):
    help = "Agrega as metricas por cliente no banco e lista alertas (cron de hora em hora)."

    def add_arguments(self, parser):
        parser.add_argument("--sem-alertas", action="store_true", help="nao mostrar alertas")

    def handle(self, *args, **options):
        gravadas = agregar_metricas()
        self.stdout.write(self.style.SUCCESS(f"Metricas gravadas: {gravadas} linha(s) por hora."))
        if not options["sem_alertas"]:
            alertas = alertas_pendentes()
            if not alertas:
                self.stdout.write("Sem alertas pendentes.")
            for alerta in alertas:
                self.stdout.write(self.style.WARNING(f"ALERTA: {alerta}"))
