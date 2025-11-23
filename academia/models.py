from django.db import models

class Configuracao(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Nome do Site")
    endereco = models.CharField(max_length=255, verbose_name="Endereço")
    numero = models.CharField(max_length=20, verbose_name="Número")
    cep = models.CharField(max_length=20, verbose_name="CEP")
    cnpj = models.CharField(max_length=20, verbose_name="CNPJ")
    ie = models.CharField(max_length=20, verbose_name="Inscrição Estadual", blank=True, null=True)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Configuração"
        verbose_name_plural = "Configurações"

class IdentidadeVisual(models.Model):
    logotipo = models.ImageField(upload_to='logos/', verbose_name="Logotipo")
    favicon = models.ImageField(upload_to='favicons/', verbose_name="Favicon")

    def __str__(self):
        return "Identidade Visual"

    class Meta:
        verbose_name = "Identidade Visual"
        verbose_name_plural = "Identidade Visual"
