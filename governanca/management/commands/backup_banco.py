"""Backup do banco com verificacao por restauracao de teste (RNF-005)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.servicos import (
    aplicar_retencao_de_backups, executar_backup, verificar_backup,
)


class Command(BaseCommand):
    help = "Faz o backup do banco, verifica o arquivo e aplica a retencao."

    def add_arguments(self, parser):
        parser.add_argument("--metodo", choices=["auto", "pg_dump", "json"], default="auto")
        parser.add_argument("--sem-verificar", action="store_true")
        parser.add_argument("--sem-retencao", action="store_true")
        parser.add_argument("--retencao-valendo", action="store_true",
                           help="aplica a retencao de verdade (padrao: apenas simula)")

    def handle(self, *args, **options):
        registro = executar_backup(metodo=options["metodo"])
        if registro.situacao != "ok":
            self.stderr.write(self.style.ERROR(f"Backup FALHOU: {registro.erro[:300]}"))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Backup ok: {registro.arquivo} ({registro.tamanho_mb} MB)"))
        if not options["sem_verificar"]:
            verificacao = verificar_backup(registro)
            estilo = self.style.SUCCESS if verificacao["ok"] else self.style.WARNING
            self.stdout.write(estilo(f"Verificacao: {verificacao['detalhe']}"))
        if not options["sem_retencao"]:
            resultado = aplicar_retencao_de_backups(dry_run=not options["retencao_valendo"])
            self.stdout.write(
                f"Retencao ({'simulada' if resultado['dry_run'] else 'aplicada'}): "
                f"{resultado['mantidos']} mantido(s), {resultado['apagados']} apagado(s).")
            for detalhe in resultado["detalhes"]:
                self.stdout.write(f"  - {detalhe}")
