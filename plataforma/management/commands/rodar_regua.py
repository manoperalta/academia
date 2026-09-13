"""Executa a regua de cobranca (avisos, bloqueio D+10, suspensao D+30)."""
from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from plataforma.servicos import aplicar_regua


class Command(BaseCommand):
    help = "Roda a regua de cobranca e os avisos de limite/trial (idempotente por marco)."

    def add_arguments(self, parser):
        parser.add_argument("--hoje", help="Data de referencia (AAAA-MM-DD). Padrao: hoje")

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        if options.get("hoje"):
            try:
                hoje = datetime.strptime(options["hoje"], "%Y-%m-%d").date()
            except ValueError as erro:
                raise CommandError(f"data invalida: {options['hoje']}") from erro
        resumo = aplicar_regua(hoje)
        self.stdout.write(
            f"disparos: {resumo['disparos']} | faturas vencidas: {resumo['faturas_vencidas']} | "
            f"bloqueios: {resumo['bloqueios']} | suspensoes: {resumo['suspensoes']}"
        )
        self.stdout.write(self.style.SUCCESS("regua concluida"))
