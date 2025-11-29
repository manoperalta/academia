from django import forms
from .models import Notificacao
from django.contrib.auth import get_user_model

User = get_user_model()

class NotificacaoForm(forms.ModelForm):
    enviar_para_todos = forms.BooleanField(
        required=False, 
        label="Enviar para todos os usuários", 
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = Notificacao
        fields = ['assunto', 'mensagem', 'destinatarios']
        widgets = {
            'assunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Digite o assunto do e-mail'}),
            'mensagem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Digite a mensagem...'}),
            'destinatarios': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'email1@exemplo.com, email2@exemplo.com'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        enviar_todos = cleaned_data.get('enviar_para_todos')
        destinatarios = cleaned_data.get('destinatarios')

        if not enviar_todos and not destinatarios:
            raise forms.ValidationError("Informe os destinatários ou selecione 'Enviar para todos'.")
        
        if enviar_todos:
            from usuarios.models import Usuario
            from professores.models import Professor
            
            emails = set()
            
            # E-mails dos CustomUsers ativos
            user_emails = User.objects.filter(is_active=True).values_list('email', flat=True)
            emails.update([e for e in user_emails if e])
            
            # E-mails dos perfis de Usuario
            usuario_emails = Usuario.objects.filter(status_user='Ativo').values_list('email_user', flat=True)
            emails.update([e for e in usuario_emails if e])
            
            # E-mails dos perfis de Professor
            prof_emails = Professor.objects.filter(status_prof='Ativo').values_list('email_prof', flat=True)
            emails.update([e for e in prof_emails if e])
            
            if not emails:
                raise forms.ValidationError("Nenhum e-mail encontrado no sistema.")
            
            cleaned_data['destinatarios'] = ', '.join(sorted(emails))
        
        return cleaned_data
