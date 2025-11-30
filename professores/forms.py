from django import forms
from .models import Professor

class ProfessorForm(forms.ModelForm):
    class Meta:
        model = Professor
        fields = [
            'nome', 'data_nasc', 'cpf_cnpj_prof', 'email_prof', 'telefone_prof',
            'endereco_prof', 'numero_end_prof', 'bairro_prof', 'cep_prof', 'status_prof'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'email_prof': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone_prof': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'endereco_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'status_prof': forms.Select(attrs={'class': 'form-select'}),
        }

class ProfessorProfileForm(forms.ModelForm):
    class Meta:
        model = Professor
        fields = [
            'nome', 'data_nasc', 'cpf_cnpj_prof', 'email_prof', 'telefone_prof',
            'endereco_prof', 'numero_end_prof', 'bairro_prof', 'cep_prof', 'foto_prof'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'email_prof': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone_prof': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'endereco_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_prof': forms.TextInput(attrs={'class': 'form-control'}),
            'foto_prof': forms.FileInput(attrs={'class': 'form-control'}),
        }
