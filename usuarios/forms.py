from django import forms
from .models import Usuario, FichaSaude

class UsuarioForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'nome', 'data_nasc', 'cpf_cnpj_user', 'email_user', 'telefone_user',
            'endereco_user', 'numero_end_user', 'bairro_user', 'cep_user', 'status_user'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_user': forms.TextInput(attrs={'class': 'form-control'}),
            'email_user': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone_user': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'endereco_user': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_user': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_user': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_user': forms.TextInput(attrs={'class': 'form-control'}),
            'status_user': forms.Select(attrs={'class': 'form-select'}),
        }

class UsuarioProfileForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = [
            'nome', 'data_nasc', 'cpf_cnpj_user', 'email_user', 'telefone_user',
            'endereco_user', 'numero_end_user', 'bairro_user', 'cep_user', 'foto_user'
        ]
        widgets = {
            'data_nasc': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cpf_cnpj_user': forms.TextInput(attrs={'class': 'form-control'}),
            'email_user': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@exemplo.com'}),
            'telefone_user': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'endereco_user': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_end_user': forms.TextInput(attrs={'class': 'form-control'}),
            'bairro_user': forms.TextInput(attrs={'class': 'form-control'}),
            'cep_user': forms.TextInput(attrs={'class': 'form-control'}),
            'foto_user': forms.FileInput(attrs={'class': 'form-control'}),
        }

class FichaSaudeForm(forms.ModelForm):
    class Meta:
        model = FichaSaude
        fields = ['altura', 'peso', 'restricoes', 'prescricoes', 'obs', 'usa_medicamento', 'qual_medicamento']
        widgets = {
            'altura': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ex: 1.75'}),
            'peso': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ex: 70.5'}),
            'restricoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prescricoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'obs': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'usa_medicamento': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'usa_medicamento'}),
            'qual_medicamento': forms.TextInput(attrs={'class': 'form-control', 'id': 'qual_medicamento_input'}),
        }
