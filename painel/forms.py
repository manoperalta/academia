from django import forms
from .models import Painel

class PainelForm(forms.ModelForm):
    class Meta:
        model = Painel
        fields = ['aula', 'data', 'hora_inicio', 'hora_fim']
        widgets = {
            'aula': forms.Select(attrs={'class': 'form-select'}),
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_fim': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }
