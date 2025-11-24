from django.db import models

from django.conf import settings

class Usuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usuario_profile', null=True, blank=True)

    STATUS_CHOICES = (
        ('Ativo', 'Ativo'),
        ('Inativo', 'Inativo'),
    )

    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    data_nasc = models.DateField(verbose_name="Data de Nascimento")
    endereco_user = models.CharField(max_length=255, verbose_name="Endereço")
    numero_end_user = models.CharField(max_length=20, verbose_name="Número")
    bairro_user = models.CharField(max_length=100, verbose_name="Bairro")
    cep_user = models.CharField(max_length=20, verbose_name="CEP")
    cpf_cnpj_user = models.CharField(max_length=20, verbose_name="CPF/CNPJ")
    data_create_user = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_user = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    foto_user = models.ImageField(upload_to='usuarios_fotos/', null=True, blank=True, verbose_name="Foto de Perfil")
    status_user = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Ativo', verbose_name="Status")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
