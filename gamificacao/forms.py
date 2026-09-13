"""Formularios de gamificacao."""

from __future__ import annotations

from django import forms

from gamificacao.models import Conquista, RegraDePontos


class RegraDePontosForm(forms.ModelForm):
    class Meta:
        model = RegraDePontos
        fields = ["evento", "pontos", "limite_diario", "ativo"]


class ConquistaForm(forms.ModelForm):
    class Meta:
        model = Conquista
        fields = ["nome", "descricao", "evento", "quantidade", "pontos_bonus", "icone", "ativa"]
