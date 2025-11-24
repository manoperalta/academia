from django import forms
from .models import Usuario

class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'nome', 'data_nasc', 'endereco_user', 'numero_end_user', 
            'bairro_user', 'cep_user', 'cpf_cnpj_user', 'status_user'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'endereco_user': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_user': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_user': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_user': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_user': forms.TextInput(attrs={'class': 'form-control'}),
            'status_user': forms.Select(attrs={'class': 'form-select'}),
        }
