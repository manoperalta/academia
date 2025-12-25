from django import forms
from .models import Pagamento, Plano

class PagamentoForm(forms.ModelForm):
    class Meta:
        model = Pagamento
        fields = ['usuario', 'plano', 'data_inicio', 'valor_pago']
        widgets = {
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'plano': forms.Select(attrs={'class': 'form-select'}),
            'data_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pago': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class PlanoForm(forms.ModelForm):
    class Meta:
        model = Plano
        fields = ['nome', 'tipo', 'valor', 'descricao', 'imagem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'imagem': forms.FileInput(attrs={'class': 'form-control'}),
        }
