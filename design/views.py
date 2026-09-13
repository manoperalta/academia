"""Vitrine do design system: mostra cada componente e onde ele ja e usado no painel."""

from __future__ import annotations

from django import forms
from django.views.generic import TemplateView

from gestao.mixins import PainelMixin


class VitrineView(PainelMixin, TemplateView):
    """Uma pagina para conferir os componentes — e o combinado de como escrever tela nova."""

    template_name = "design/vitrine.html"

    class ExemploDeFormulario(forms.Form):
        """Campo de exemplo, so para a vitrine mostrar o componente de campo."""

        nome = forms.CharField(label="Nome do aluno", required=True,
                               help_text="como aparece no cadastro")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["form"] = self.ExemploDeFormulario()
        contexto["variacoes"] = [
            {"tom": "neutro", "texto": "neutro"},
            {"tom": "sucesso", "texto": "liberado"},
            {"tom": "atencao", "texto": "enviando 40%"},
            {"tom": "erro", "texto": "vencida"},
            {"tom": "info", "texto": "autorizado pelo parceiro"},
        ]
        return contexto
