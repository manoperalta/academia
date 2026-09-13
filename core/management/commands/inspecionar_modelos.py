"""Inspeciona os campos dos modelos (para construir formularios e telas com precisao).

Uso: python manage.py inspecionar_modelos [app ...]     (sem app = todos os apps com modelo)
"""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand

PADRAO = [
    "accounts",
    "usuarios",
    "professores",
    "aulas",
    "agendamento",
    "financeiro",
    "academia",
    "notificacoes",
]


class Command(BaseCommand):
    help = "Lista os campos concretos de cada modelo, com tipo, nulos, defaults e choices."

    def add_arguments(self, parser):
        parser.add_argument("apps", nargs="*", default=PADRAO)

    def handle(self, *args, **options):
        alvos = options["apps"] or PADRAO
        for nome_app in alvos:
            try:
                config = apps.get_app_config(nome_app)
            except LookupError:
                self.stdout.write(f"[{nome_app}] app nao encontrado")
                continue
            for modelo in config.get_models():
                self.stdout.write(f"\n[{nome_app}.{modelo.__name__}]")
                for campo in modelo._meta.concrete_fields:
                    marcas = []
                    if campo.primary_key:
                        marcas.append("PK")
                    if campo.null:
                        marcas.append("null")
                    if campo.blank:
                        marcas.append("blank")
                    if campo.has_default():
                        marcas.append(f"default={campo.get_default()!r}")
                    if campo.is_relation and campo.related_model is not None:
                        marcas.append(f"->{campo.related_model.__name__}")
                    if getattr(campo, "choices", None):
                        valores = [str(c[0]) for c in campo.choices][:6]
                        marcas.append(f"choices={valores}")
                    if campo.verbose_name:
                        marcas.append(f"label={campo.verbose_name}")
                    self.stdout.write(
                        f"  {campo.name}: {campo.get_internal_type()} {' '.join(marcas)}"
                    )
