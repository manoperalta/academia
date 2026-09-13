"""Reconfere os dominios proprios e reemite certificados com falha (RF-PLT-051)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.models import Rede, StatusCertificado, StatusDominio
from governanca.servicos import reemitir_certificado, verificar_dominio


class Command(BaseCommand):
    help = "Verifica os dominios proprios e marca para reemissao os certificados com erro."

    def add_arguments(self, parser):
        parser.add_argument("--emitir", action="store_true",
                           help="marca para reemissao os certificados em erro")

    def handle(self, *args, **options):
        verificados = reemitidos = 0
        for rede in Rede.todos.exclude(dominio=""):
            resultado = verificar_dominio(rede, forcar=True)
            verificados += 1
            self.stdout.write(f"{rede.nome} ({rede.dominio}): {resultado['mensagem'][:110]}")
            if (options["emitir"] and rede.certificado_status == StatusCertificado.ERRO
                    and rede.dominio_status == StatusDominio.PRONTO):
                reemitir_certificado(rede)
                reemitidos += 1
                self.stdout.write(f"  -> certificado marcado para reemissao")
        self.stdout.write(self.style.SUCCESS(
            f"Dominios verificados: {verificados}; certificados reemitidos: {reemitidos}."))
