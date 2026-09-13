"""Semeia pacotes, configuracao da plataforma e trials (idempotente)."""
from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Rede
from plataforma.models import Assinatura, ConfiguracaoPlataforma, ModuloPacote, Pacote

TODOS = [modulo.value for modulo in ModuloPacote]

PACOTES = [
    {
        "nome": "Prata", "codigo": "prata", "limite_alunos": 100, "limite_professores": 5,
        "limite_unidades": 1, "ordem": 1,
        "descricao": "Para academias de bairro com uma unidade",
        "modulos": [ModuloPacote.IMPRESSAO_PDF],
    },
    {
        "nome": "Bronze", "codigo": "bronze", "limite_alunos": 150, "limite_professores": 10,
        "limite_unidades": 1, "ordem": 2,
        "descricao": "Para academias em crescimento",
        "modulos": [ModuloPacote.IMPRESSAO_PDF, ModuloPacote.WHATSAPP,
                    ModuloPacote.RELATORIOS_AVANCADOS],
    },
    {
        "nome": "Ouro", "codigo": "ouro", "limite_alunos": None, "limite_professores": None,
        "limite_unidades": None, "ordem": 3,
        "descricao": "Sem teto, com API, dominios e rede de unidades",
        "modulos": TODOS,
    },
]


class Command(BaseCommand):
    help = "Cria/atualiza os pacotes comerciais, a configuracao da plataforma e assinaturas de teste."

    def add_arguments(self, parser):
        parser.add_argument("--prata", type=float, default=0.0, metavar="VALOR",
                            help="Preco mensal do Prata (padrao 0 = a definir)")
        parser.add_argument("--bronze", type=float, default=0.0, metavar="VALOR")
        parser.add_argument("--ouro", type=float, default=0.0, metavar="VALOR")
        parser.add_argument("--sem-trial", action="store_true",
                            help="Nao cria assinatura de teste para redes sem assinatura")

    def handle(self, *args, **options):
        precos = {"prata": options["prata"], "bronze": options["bronze"], "ouro": options["ouro"]}
        for definicao in PACOTES:
            mensal = Decimal(str(precos.get(definicao["codigo"], 0)))
            anual = (mensal * 12 * Decimal("0.85")).quantize(Decimal("0.01")) if mensal else Decimal("0")
            pacote, criado = Pacote.objects.update_or_create(
                codigo=definicao["codigo"],
                defaults={
                    "nome": definicao["nome"],
                    "descricao": definicao["descricao"],
                    "limite_alunos": definicao["limite_alunos"],
                    "limite_professores": definicao["limite_professores"],
                    "limite_unidades": definicao["limite_unidades"],
                    "preco_mensal": mensal,
                    "preco_anual": anual,
                    "modulos": definicao["modulos"],
                    "ordem_exibicao": definicao["ordem"],
                },
            )
            self.stdout.write(f"{'criado' if criado else 'atualizado'}: {pacote.nome} "
                              f"({pacote.limite_alunos or 'ilimitado'} alunos / "
                              f"{pacote.limite_professores or 'ilimitado'} professores) "
                              f"R$ {pacote.preco_mensal}")

        configuracao = ConfiguracaoPlataforma.obter()
        if not configuracao.token_webhook:
            configuracao.token_webhook = secrets.token_urlsafe(24)
            configuracao.save(update_fields=["token_webhook"])
            self.stdout.write("token do webhook gerado (veja em Configuracao da plataforma)")
        if configuracao.gateway_em_modo_simulado:
            self.stdout.write(self.style.WARNING(
                "sem chave Asaas: a cobranca roda em MODO SIMULADO (dev/teste)"
            ))

        if options["sem_trial"]:
            return
        ouro = Pacote.objects.get(codigo="ouro")
        hoje = timezone.localdate()
        criadas = 0
        for rede in Rede.todos.all():
            if Assinatura.objects.filter(rede=rede).exists():
                continue
            Assinatura.objects.create(
                rede=rede, pacote=ouro, ciclo="mensal", inicio=hoje,
                renovacao_em=hoje + timedelta(days=configuracao.trial_dias),
                trial_termina_em=hoje + timedelta(days=configuracao.trial_dias),
            )
            rede.status = "trial"
            rede.trial_termina_em = timezone.now() + timedelta(days=configuracao.trial_dias)
            rede.save(update_fields=["status", "trial_termina_em"])
            criadas += 1
        self.stdout.write(f"assinaturas de teste criadas: {criadas}")
