"""Move a midia antiga para o namespace de cada cliente (RNF-010)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.servicos import mover_midia_para_namespace


class Command(BaseCommand):
    help = "Organiza media/<arquivo> em media/redes/<cliente>/... (padrao: simula)."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="move de verdade")

    def handle(self, *args, **options):
        resultado = mover_midia_para_namespace(dry_run=not options["aplicar"])
        self.stdout.write(
            f"{'Movidos' if not resultado['dry_run'] else 'Moveria'}: {resultado['movidos']} "
            f"arquivo(s); ignorados: {resultado['ignorados']}.")
        for detalhe in resultado["detalhes"][:40]:
            self.stdout.write(f"  - {detalhe}")
        if resultado["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulacao: rode com --aplicar para mover."))
