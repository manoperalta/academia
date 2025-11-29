from django.db import models

class Configuracao(models.Model):
    titulo = models.CharField(max_length=255, verbose_name="Nome do Site")
    endereco = models.CharField(max_length=255, verbose_name="Endereço")
    numero = models.CharField(max_length=20, verbose_name="Número")
    cep = models.CharField(max_length=20, verbose_name="CEP")
    cnpj = models.CharField(max_length=20, verbose_name="CNPJ")
    ie = models.CharField(max_length=20, verbose_name="Inscrição Estadual", blank=True, null=True)
    
    # Configurações de Alertas Financeiros
    dias_alerta_vencimento = models.IntegerField(
        default=5, 
        verbose_name="Dias para Alerta de Vencimento",
        help_text="Quantidade de dias antes do vencimento para exibir alerta amarelo"
    )
    mensagem_pagamento_atrasado = models.TextField(
        default="Seu pagamento está em atraso. Por favor, regularize sua situação o quanto antes para continuar aproveitando nossos serviços.",
        verbose_name="Mensagem de Pagamento Atrasado",
        help_text="Mensagem enviada por e-mail para usuários com pagamento atrasado"
    )
    
    # Configurações de Aniversariantes
    mensagem_aniversario = models.TextField(
        default="Parabéns pelo seu aniversário! Desejamos um dia maravilhoso e cheio de alegrias. A equipe {academia} te deseja muita saúde e felicidade!",
        verbose_name="Mensagem de Aniversário",
        help_text="Mensagem enviada por e-mail para aniversariantes. Use {academia} para o nome do site e {nome} para o nome da pessoa."
    )

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
