from django import forms
from .models import Painel

from aulas.models import Aulas

class PainelForm(forms.ModelForm):
    aulas_selecionadas = forms.ModelMultipleChoiceField(
        queryset=Aulas.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Aulas do Circuito"
    )

    class Meta:
        model = Painel
        fields = ['nome', 'data', 'hora_inicio', 'hora_fim', 'numero_de_user']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Circuito Manhã'}),
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_fim': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'numero_de_user': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Opcional (vazio = ilimitado)'}),
        }
