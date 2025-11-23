from django import forms
from .models import Painel
from aulas.models import Aulas

class PainelForm(forms.ModelForm):
    class Meta:
        model = Painel
        fields = ['data_painel', 'horario_inicial_painel', 'horario_final_painel', 'numero_de_user', 'aulas']
        widgets = {
            'data_painel': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'horario_inicial_painel': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'horario_final_painel': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'numero_de_user': forms.NumberInput(attrs={'class': 'form-control'}),
            'aulas': forms.SelectMultiple(attrs={'class': 'form-control', 'style': 'height: 200px;'}),
        }

    def __init__(self, user, *args, **kwargs):
        super(PainelForm, self).__init__(*args, **kwargs)
        # Filtrar aulas apenas do professor logado
        if user:
            self.fields['aulas'].queryset = Aulas.objects.filter(professor=user)
