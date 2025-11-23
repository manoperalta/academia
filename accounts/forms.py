from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    USER_TYPE_CHOICES = (
        ('usuario', 'Usuário'),
        ('professor', 'Professor'),
    )
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, label="Tipo de Conta")

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('user_type',)
