"""Tela da busca global."""

from __future__ import annotations

from django.views.generic import TemplateView

from busca import servicos
from gestao.mixins import PainelMixin


class BuscaView(PainelMixin, TemplateView):
    """Uma caixa de busca para todo o painel, respeitando papel e rede."""

    template_name = "busca/resultados.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        termo = self.request.GET.get("q", "")
        contexto["resultado"] = servicos.buscar(self.request.rede, termo, usuario=self.request.user)
        contexto["termo"] = termo.strip()
        return contexto
