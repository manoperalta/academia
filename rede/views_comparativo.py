"""Comparativo de unidades: ranking da rede por receita, alunos, ticket e inadimplencia.

Arquivo proprio pelo mesmo motivo da auditoria: nao toca no views.py ja publicado do painel da rede.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.views.generic import TemplateView

from core.models import Unidade
from gestao.permissoes import Modulo
from gestao.views import PainelMixin


class ComparativoDeUnidadesView(PainelMixin, TemplateView):
    """Quem puxa a rede e quem esta ficando para tras, com o numero na frente."""

    modulo = Modulo.UNIDADES
    template_name = "rede/comparativo.html"

    def get_context_data(self, **kwargs):
        from financeiro.models import Pagamento

        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        referencia = hoje.replace(day=1)
        mes_anterior = (referencia - timedelta(days=1)).replace(day=1)
        unidades = Unidade.objects.filter(rede=self.request.rede, status="ativa")
        linhas = []
        total_receita = Decimal("0")
        total_alunos = 0
        for unidade in unidades:
            do_mes = Pagamento.todos.filter(
                rede=self.request.rede,
                unidade=unidade,
                status="pago",
                data_inicio__gte=referencia,
                data_inicio__lte=hoje,
            )
            receita = sum(
                (pagamento.valor_pago or Decimal("0") for pagamento in do_mes), Decimal("0")
            )
            alunos = do_mes.values("usuario").distinct().count()
            anterior = Pagamento.todos.filter(
                rede=self.request.rede,
                unidade=unidade,
                status="pago",
                data_inicio__gte=mes_anterior,
                data_inicio__lt=referencia,
            )
            receita_anterior = sum(
                (pagamento.valor_pago or Decimal("0") for pagamento in anterior), Decimal("0")
            )
            atrasadas = Pagamento.todos.filter(
                rede=self.request.rede,
                unidade=unidade,
                data_fim__lt=hoje,
            ).exclude(status="pago")
            valor_atrasado = sum(
                (pagamento.valor_pago or Decimal("0") for pagamento in atrasadas), Decimal("0")
            )
            base = receita + valor_atrasado
            linhas.append(
                {
                    "unidade": unidade,
                    "receita": receita,
                    "alunos": alunos,
                    "ticket_medio": (receita / alunos).quantize(Decimal("0.01"))
                    if alunos
                    else Decimal("0.00"),
                    "inadimplencia_valor": valor_atrasado,
                    "inadimplencia_percentual": (
                        round(float(valor_atrasado) * 100 / float(base), 1) if base else 0.0
                    ),
                    "variacao": (
                        round(float(receita - receita_anterior) * 100 / float(receita_anterior), 1)
                        if receita_anterior
                        else 0.0
                    ),
                }
            )
            total_receita += receita
            total_alunos += alunos
        linhas.sort(key=lambda linha: (-linha["receita"], linha["unidade"].nome))
        contexto.update(
            {
                "ranking": linhas,
                "referencia": referencia,
                "total_receita": total_receita,
                "total_alunos": total_alunos,
                "ticket_medio_da_rede": (
                    (total_receita / total_alunos).quantize(Decimal("0.01"))
                    if total_alunos
                    else Decimal("0.00")
                ),
            }
        )
        return contexto
