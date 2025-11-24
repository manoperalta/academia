from django import forms
from .models import Professor

class ProfessorForm(forms.ModelForm):
    class Meta:
        model = Professor
        fields = [
            'nome', 'data_nasc', 'endereco_prof', 'numero_end_prof', 
            'bairro_prof', 'cep_prof', 'cpf_cnpj_prof', 'status_prof'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'status_prof': forms.Select(attrs={'class': 'form-select'}),
        }
