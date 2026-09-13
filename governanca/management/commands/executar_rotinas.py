"""Roda as rotinas periodicas (cron): metricas, backup, faturas, regua, repasses e expurgo."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.rotinas import executar_rotinas


class Command(BaseCommand):
    help = "Executa as rotinas devidas, com dry-run opcional. Sugestao: de hora em hora."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="so mostra o que seria feito")
        parser.add_argument("--somente", default="", help="executa apenas uma rotina pelo nome")

    def handle(self, *args, **options):
        resultado = executar_rotinas(dry_run=options["dry_run"], somente=options["somente"])
        if not resultado["executadas"]:
            self.stdout.write("Nenhuma rotina devida neste momento.")
            return
        for item in resultado["executadas"]:
            prefixo = "SIMULA" if item["simulado"] else item["situacao"].upper()
            self.stdout.write(f"[{prefixo}] {item['rotina']} ({item['duracao_ms']} ms): {item['detalhe']}")
        if resultado["falhas"]:
            self.stderr.write(self.style.ERROR(f"{len(resultado['falhas'])} rotina(s) falharam"))
        else:
            self.stdout.write(self.style.SUCCESS("Rotinas concluidas sem falha."))
