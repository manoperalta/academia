"""Exportacao logica de um cliente (restauracao pontual, RNF-005)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import Rede
from governanca.servicos import exportar_tenant, verificar_backup


class Command(BaseCommand):
    help = "Exporta todos os dados de um cliente num arquivo, sem afetar os demais."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--sem-verificar", action="store_true")

    def handle(self, *args, **options):
        rede = Rede.todos.filter(slug=options["slug"]).first()
        if rede is None:
            self.stderr.write(self.style.ERROR(f"Cliente {options['slug']!r} nao encontrado."))
            return
        registro = exportar_tenant(rede)
        if registro.situacao != "ok":
            self.stderr.write(self.style.ERROR(f"Exportacao FALHOU: {registro.erro[:300]}"))
            return
        self.stdout.write(
            self.style.SUCCESS(f"{rede.nome}: {registro.arquivo} ({registro.tamanho_mb} MB)")
        )
        if not options["sem_verificar"]:
            verificacao = verificar_backup(registro)
            self.stdout.write(f"Verificacao: {verificacao['detalhe']}")
