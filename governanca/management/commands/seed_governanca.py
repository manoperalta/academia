"""Semeia as regras de retencao padrao (LGPD/RNF-006)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from governanca.models import RegraRetencao

REGRAS = [
    ("tentativas_login", "Historico de tentativas de acesso", 180, "seguranca da informacao",
     RegraRetencao.Acao.ELIMINAR),
    ("acesso_dado_sensivel", "Leituras de ficha de saude", 1825,
     "prestacao de contas (LGPD art. 37)", RegraRetencao.Acao.CONSERVAR),
    ("erro_tenant", "Erros tecnicos por cliente", 90, "operacao do servico",
     RegraRetencao.Acao.ELIMINAR),
    ("metrica_tenant", "Metricas de uso por cliente", 400, "operacao do servico",
     RegraRetencao.Acao.ELIMINAR),
    ("solicitacao_titular", "Pedidos de titulares", 1825, "prestacao de contas (LGPD art. 37)",
     RegraRetencao.Acao.CONSERVAR),
    ("pagamento", "Registros financeiros", 1825, "obrigacao fiscal e contabil",
     RegraRetencao.Acao.CONSERVAR),
]


class Command(BaseCommand):
    help = "Cria/atualiza as regras de retencao de dados (LGPD)."

    def handle(self, *args, **options):
        criadas = atualizadas = 0
        for entidade, descricao, prazo, base_legal, acao in REGRAS:
            _regra, criada = RegraRetencao.objects.update_or_create(
                entidade=entidade,
                defaults={"descricao": descricao, "prazo_dias": prazo, "base_legal": base_legal,
                          "acao": acao, "ativo": True},
            )
            criadas += int(criada)
            atualizadas += int(not criada)
        self.stdout.write(self.style.SUCCESS(
            f"Regras de retencao: {criadas} criada(s), {atualizadas} atualizada(s)."))
        self.stdout.write(
            "Pagamentos sao CONSERVADOS pelo prazo fiscal mesmo apos anonimizar o titular."
        )
