from django.db import models

from django.conf import settings

class Professor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='professor_profile', null=True, blank=True)

    STATUS_CHOICES = (
        ('Ativo', 'Ativo'),
        ('Inativo', 'Inativo'),
    )

    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    data_nasc = models.DateField(verbose_name="Data de Nascimento", null=True, blank=True)
    endereco_prof = models.CharField(max_length=255, verbose_name="Endereço", null=True, blank=True)
    numero_end_prof = models.CharField(max_length=20, verbose_name="Número", null=True, blank=True)
    bairro_prof = models.CharField(max_length=100, verbose_name="Bairro", null=True, blank=True)
    cep_prof = models.CharField(max_length=20, verbose_name="CEP", null=True, blank=True)
    cpf_cnpj_prof = models.CharField(max_length=20, verbose_name="CPF/CNPJ", null=True, blank=True)
    email_prof = models.EmailField(verbose_name="E-mail", blank=True, null=True)
    telefone_prof = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    data_create_prof = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_prof = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    foto_prof = models.ImageField(upload_to='professores_fotos/', null=True, blank=True, verbose_name="Foto de Perfil")
    status_prof = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Ativo', verbose_name="Status")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Professor"
        verbose_name_plural = "Professores"
