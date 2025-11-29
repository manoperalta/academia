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

class Notificacao(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviado', 'Enviado'),
        ('falha', 'Falha'),
    ]

    assunto = models.CharField(max_length=255, verbose_name="Assunto")
    mensagem = models.TextField(verbose_name="Mensagem")
    destinatarios = models.TextField(verbose_name="Destinatários (separados por vírgula)", help_text="Emails separados por vírgula")
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Criado por")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_envio = models.DateTimeField(null=True, blank=True, verbose_name="Data de Envio")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    erro_log = models.TextField(blank=True, verbose_name="Log de Erro")

    def enviar(self):
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
                subject=self.assunto,
                body=self.mensagem,
                from_email=f"{config.remetente_nome} <{config.remetente_email}>",
                to=dest_list,
                connection=connection
            )
            
            # Se quiser enviar HTML também
            # email.attach_alternative(html_content, "text/html")
            
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

    def __str__(self):
        return f"{self.assunto} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"
        ordering = ['-data_criacao']
