"""Formularios de pesquisa."""

from __future__ import annotations

from django import forms

from nps.models import Pesquisa


class PesquisaForm(forms.ModelForm):
    class Meta:
        model = Pesquisa
        fields = ["titulo", "pergunta", "tipo", "unidade", "ativa", "inicio", "fim"]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }
