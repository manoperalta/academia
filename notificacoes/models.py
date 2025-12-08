from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import get_connection, EmailMultiAlternatives

class ConfiguracaoEmail(models.Model):
    host = models.CharField(max_length=255, verbose_name="Servidor SMTP (Host)")
    port = models.IntegerField(default=587, verbose_name="Porta")
    username = models.CharField(max_length=255, verbose_name="Usuário/Email")
    password = models.CharField(max_length=255, verbose_name="Senha")
    use_tls = models.BooleanField(default=True, verbose_name="Usar TLS")
    use_ssl = models.BooleanField(default=False, verbose_name="Usar SSL")
    remetente_nome = models.CharField(max_length=255, default="Academia System", verbose_name="Nome do Remetente")
    remetente_email = models.EmailField(verbose_name="Email do Remetente")
    
    ativo = models.BooleanField(default=True, verbose_name="Configuração Ativa")

    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracaoEmail.objects.exists():
            raise ValidationError('Apenas uma configuração de e-mail é permitida.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Configuração SMTP ({self.host})"

    class Meta:
        verbose_name = "Configuração de E-mail"
        verbose_name_plural = "Configuração de E-mail"

class ConfiguracaoWhatsapp(models.Model):
    access_token = models.CharField(max_length=500, verbose_name="Access Token")
    phone_number_id = models.CharField(max_length=100, verbose_name="Phone Number ID")
    business_account_id = models.CharField(max_length=100, verbose_name="WhatsApp Business Account ID", blank=True, null=True)
    
    ativo = models.BooleanField(default=True, verbose_name="Configuração Ativa")

    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracaoWhatsapp.objects.exists():
            raise ValidationError('Apenas uma configuração de WhatsApp é permitida.')
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Configuração WhatsApp ({self.phone_number_id})"

    class Meta:
        verbose_name = "Configuração de WhatsApp"
        verbose_name_plural = "Configuração de WhatsApp"

class Notificacao(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviado', 'Enviado'),
        ('falha', 'Falha'),
    ]

    TIPO_CHOICES = [
        ('email', 'E-mail'),
        ('whatsapp', 'WhatsApp'),
    ]

    assunto = models.CharField(max_length=255, verbose_name="Assunto", blank=True, null=True)
    mensagem = models.TextField(verbose_name="Mensagem")
    destinatarios = models.TextField(verbose_name="Destinatários", help_text="Emails ou números separados por vírgula")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='email', verbose_name="Tipo")
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Criado por")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_envio = models.DateTimeField(null=True, blank=True, verbose_name="Data de Envio")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    erro_log = models.TextField(blank=True, verbose_name="Log de Erro")

    def enviar(self):
        if self.tipo == 'email':
            return self.enviar_email()
        elif self.tipo == 'whatsapp':
            return self.enviar_whatsapp()
        return False

    def enviar_email(self):
        config = ConfiguracaoEmail.objects.first()
        if not config or not config.ativo:
            self.status = 'falha'
            self.erro_log = "Configuração de e-mail não encontrada ou inativa."
            self.save()
            return False

        try:
            connection = get_connection(
                host=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                use_tls=config.use_tls,
                use_ssl=config.use_ssl
            )
            
            dest_list = [email.strip() for email in self.destinatarios.split(',') if email.strip()]
            
            email = EmailMultiAlternatives(
                subject=self.assunto or "Notificação",
                body=self.mensagem,
                from_email=f"{config.remetente_nome} <{config.remetente_email}>",
                to=dest_list,
                connection=connection
            )
            
            email.send()
            
            self.status = 'enviado'
            from django.utils import timezone
            self.data_envio = timezone.now()
            self.save()
            return True
            
        except Exception as e:
            self.status = 'falha'
            self.erro_log = str(e)
            self.save()
            return False

    def enviar_whatsapp(self):
        # Placeholder para implementação futura da API do WhatsApp
        # Aqui você implementaria a chamada real para a API do WhatsApp Business
        config = ConfiguracaoWhatsapp.objects.first()
        if not config or not config.ativo:
            self.status = 'falha'
            self.erro_log = "Configuração de WhatsApp não encontrada ou inativa."
            self.save()
            return False
            
        # Simulação de envio
        try:
            # TODO: Implementar chamada requests.post para API do Facebook/WhatsApp
            # Exemplo:
            # url = f"https://graph.facebook.com/v17.0/{config.phone_number_id}/messages"
            # headers = {"Authorization": f"Bearer {config.access_token}", "Content-Type": "application/json"}
            # payload = ...
            # response = requests.post(url, headers=headers, json=payload)
            
            # Por enquanto, apenas marca como enviado se tiver configuração
            self.status = 'enviado'
            from django.utils import timezone
            self.data_envio = timezone.now()
            self.save()
            return True
        except Exception as e:
            self.status = 'falha'
            self.erro_log = str(e)
            self.save()
            return False

    def __str__(self):
        return f"{self.assunto or 'Mensagem'} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-data_criacao']
