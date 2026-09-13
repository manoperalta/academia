"""Republica as agendas dos professores (materializa a janela de semanas a frente).

Pensado para rodar de tempo em tempo (cron): a agenda aberta do professor vai sendo empurrada para
frente sozinha, sem ninguem precisar reabrir horario. ``--dry-run`` mostra o que mudaria.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from painel_do_professor import servicos
from professores.models import Professor


class Command(BaseCommand):
    help = "Materializa a agenda dos professores ativos na janela de semanas a frente."

    def add_arguments(self, parser):
        parser.add_argument("--semanas", type=int, default=servicos.SEMANAS_PADRAO)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--rede", type=str, default="")

    def handle(self, *args, **opcoes):
        professores = Professor.todos.filter(status_prof="Ativo", user__isnull=False)
        if opcoes["rede"]:
            professores = professores.filter(rede__slug=opcoes["rede"])
        total = {"criadas": 0, "atualizadas": 0, "arquivadas": 0, "preservadas": 0}
        avisos = []
        for professor in professores.select_related("rede"):
            resultado = servicos.materializar_agenda(
                professor, semanas=opcoes["semanas"], dry_run=opcoes["dry_run"]
            )
            for chave in total:
                total[chave] += resultado[chave]
            avisos.extend(resultado["avisos"])
        modo = " (simulacao)" if opcoes["dry_run"] else ""
        self.stdout.write(
            f"Agenda{modo}: {total['criadas']} criada(s), {total['atualizadas']} atualizada(s), "
            f"{total['arquivadas']} arquivada(s), {total['preservadas']} preservada(s)."
        )
        for aviso in avisos[:20]:
            self.stdout.write(f"  aviso: {aviso}")
