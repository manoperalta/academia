"""Expurgo conforme as regras de retencao (RNF-006)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.servicos import aplicar_retencao


class Command(BaseCommand):
    help = "Mostra (ou aplica) o expurgo de dados vencidos conforme a retencao."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="apaga de verdade (padrao: simula)")

    def handle(self, *args, **options):
        resultado = aplicar_retencao(dry_run=not options["aplicar"])
        if not resultado["regras"]:
            self.stdout.write("Nada vencido para expurgar.")
            return
        for regra in resultado["regras"]:
            self.stdout.write(
                f"{regra['entidade']}: {regra['registros']} registro(s) com mais de "
                f"{regra['prazo_dias']} dias -> {regra['acao']} (base: {regra['base_legal']})")
        if resultado["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulacao: rode com --aplicar para executar."))
