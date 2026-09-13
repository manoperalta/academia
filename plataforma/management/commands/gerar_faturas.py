"""Gera as faturas dos ciclos que vencem (idempotente)."""
from __future__ import annotations

from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from plataforma.servicos import gerar_faturas_do_dia


class Command(BaseCommand):
    help = "Gera as faturas das assinaturas com renovacao vencida e emite a cobranca."

    def add_arguments(self, parser):
        parser.add_argument("--hoje", help="Data de referencia (AAAA-MM-DD). Padrao: hoje")
        parser.add_argument("--sem-cobranca", action="store_true",
                            help="Somente cria as faturas (nao chama o gateway)")

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        if options.get("hoje"):
            try:
                hoje = datetime.strptime(options["hoje"], "%Y-%m-%d").date()
            except ValueError as erro:
                raise CommandError(f"data invalida: {options['hoje']}") from erro
        if not isinstance(hoje, date):  # pragma: no cover
            raise CommandError("data invalida")
        faturas = gerar_faturas_do_dia(hoje, emitir_cobranca=not options["sem_cobranca"])
        if not faturas:
            self.stdout.write("nenhuma fatura a gerar")
        for fatura in faturas:
            self.stdout.write(
                f"fatura {fatura.numero} | {fatura.rede.nome} | R$ {fatura.valor_final} "
                f"| vence {fatura.vencimento} | gateway {fatura.gateway or 'nao emitido'}"
            )
        self.stdout.write(self.style.SUCCESS(f"total: {len(faturas)}"))
