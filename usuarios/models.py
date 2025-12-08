from django.db import models

from django.conf import settings

class Usuario(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='usuario_profile', null=True, blank=True)

    STATUS_CHOICES = (
        ('Ativo', 'Ativo'),
        ('Inativo', 'Inativo'),
    )

    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    data_nasc = models.DateField(verbose_name="Data de Nascimento", null=True, blank=True)
    endereco_user = models.CharField(max_length=255, verbose_name="Endereço", null=True, blank=True)
    numero_end_user = models.CharField(max_length=20, verbose_name="Número", null=True, blank=True)
    bairro_user = models.CharField(max_length=100, verbose_name="Bairro", null=True, blank=True)
    cep_user = models.CharField(max_length=20, verbose_name="CEP", null=True, blank=True)
    cpf_cnpj_user = models.CharField(max_length=20, verbose_name="CPF/CNPJ", null=True, blank=True)
    email_user = models.EmailField(verbose_name="E-mail", blank=True, null=True)
    telefone_user = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    data_create_user = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_user = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    foto_user = models.ImageField(upload_to='usuarios_fotos/', null=True, blank=True, verbose_name="Foto de Perfil")
    status_user = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Ativo', verbose_name="Status")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

class FichaSaude(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='ficha_saude')
    altura = models.DecimalField(max_digits=4, decimal_places=2, verbose_name="Altura (m)", null=True, blank=True)
    peso = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Peso (kg)", null=True, blank=True)
    restricoes = models.TextField(verbose_name="Restrições", null=True, blank=True)
    prescricoes = models.TextField(verbose_name="Prescrições", null=True, blank=True)
    obs = models.TextField(verbose_name="Observações", null=True, blank=True)
    usa_medicamento = models.BooleanField(default=False, verbose_name="Usa Medicamento?")
    qual_medicamento = models.CharField(max_length=255, verbose_name="Qual Medicamento?", null=True, blank=True)

    def __str__(self):
        return f"Ficha de Saúde - {self.usuario.nome}"

    class Meta:
        verbose_name = "Ficha de Saúde"
        verbose_name_plural = "Fichas de Saúde"
