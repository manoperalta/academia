"""Cria a rede padrao e etiqueta os dados que ja existiam (migracao de dados).

Uso (uma vez, ao subir a versao multi-tenant de uma instalacao que ja operava):

    python manage.py tenantizar --slug padrao --nome "Minha Academia" --dry-run
    python manage.py tenantizar --slug padrao --nome "Minha Academia"

E idempotente: rodar de novo nao duplica nada e so completa o que faltar.
"""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from core.context import definir_contexto, limpar_contexto
from core.models import Rede, Unidade


class Command(BaseCommand):
    help = "Cria a rede padrao/unidade matriz e preenche rede_id dos dados existentes."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="padrao")
        parser.add_argument("--nome", default="Academia (rede padrao)")
        parser.add_argument("--unidade", default="Matriz")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opcoes):
        slug = opcoes["slug"]
        simular = opcoes["dry_run"]

        if simular:
            self.stdout.write(self.style.WARNING("SIMULACAO: nada sera gravado"))

        with transaction.atomic():
            rede, criada = Rede.todos.get_or_create(slug=slug, defaults={"nome": opcoes["nome"]})
            self.stdout.write(
                f"rede: {rede.nome} (slug={rede.slug}) " + ("criada" if criada else "ja existia")
            )
            unidade, criada_u = Unidade.todos.get_or_create(
                rede=rede, codigo="matriz", defaults={"nome": opcoes["unidade"]}
            )
            self.stdout.write(
                f"unidade: {unidade.nome} " + ("criada" if criada_u else "ja existia")
            )

            definir_contexto(rede=rede, unidade=unidade)
            try:
                total = 0
                for modelo in apps.get_models():
                    if modelo._meta.abstract or modelo._meta.proxy:
                        continue
                    nomes = {campo.name for campo in modelo._meta.concrete_fields}
                    if "rede" not in nomes:
                        continue
                    gerenciador = (
                        modelo.todos.all() if hasattr(modelo, "todos") else modelo.objects.all()
                    )
                    sem_rede = gerenciador.filter(rede__isnull=True)
                    quantidade = sem_rede.count()
                    if not quantidade:
                        continue
                    if not simular:
                        sem_rede.update(rede=rede)
                    total += quantidade
                    self.stdout.write(f"  {modelo._meta.label}: {quantidade} registro(s)")
                self.stdout.write(self.style.SUCCESS(f"total etiquetado: {total}"))
            finally:
                limpar_contexto()

            if simular:
                raise SystemExit(0) if False else None
