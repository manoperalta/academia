from django import forms
from django.forms import inlineformset_factory
from .models import Aulas, ImagemAula

class AulasForm(forms.ModelForm):
    class Meta:
        model = Aulas
        fields = ['nome', 'descricao', 'file_de_video', 'categorias_exercicios']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'file_de_video': forms.FileInput(attrs={'class': 'form-control'}),
            'categorias_exercicios': forms.Select(attrs={'class': 'form-select'}),
        }

class ImagemAulaForm(forms.ModelForm):
    class Meta:
        model = ImagemAula
        fields = ['imagem']
        widgets = {
            'imagem': forms.FileInput(attrs={'class': 'form-control'}),
        }

ImagemAulaFormSet = inlineformset_factory(
    Aulas, ImagemAula, form=ImagemAulaForm,
    extra=1, max_num=5, can_delete=True
)
