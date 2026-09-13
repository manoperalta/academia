"""Modelos de suporte: chamado e conversa.

Chamado sem historico de conversa vira telefone sem fio. Aqui cada resposta e uma linha, com autor e
hora, e a situacao muda com registro de quem mexeu.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede, Unidade


class ChamadoDeSuporte(models.Model):
    """O que a unidade ou o aluno precisou resolver com o suporte."""

    class Categoria(models.TextChoices):
        DUVIDA = "duvida", "Duvida de uso"
        FINANCEIRO = "financeiro", "Financeiro"
        TECNICO = "tecnico", "Problema tecnico"
        ESTRUTURA = "estrutura", "Estrutura ou equipamento"
        SUGESTAO = "sugestao", "Sugestao"

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    class Situacao(models.TextChoices):
        ABERTO = "aberto", "Aberto"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        AGUARDANDO = "aguardando", "Aguardando o solicitante"
        RESOLVIDO = "resolvido", "Resolvido"
        FECHADO = "fechado", "Fechado"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="chamados")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="chamados"
    )
    titulo = models.CharField("titulo", max_length=150)
    categoria = models.CharField(
        "categoria", max_length=12, choices=Categoria.choices, default=Categoria.DUVIDA
    )
    prioridade = models.CharField(
        "prioridade", max_length=8, choices=Prioridade.choices, default=Prioridade.NORMAL
    )
    descricao = models.TextField("descricao")
    situacao = models.CharField(
        "situacao", max_length=15, choices=Situacao.choices, default=Situacao.ABERTO
    )
    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chamados_abertos",
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chamados",
        verbose_name="aluno",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chamados_sob_responsabilidade",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    resolvido_em = models.DateTimeField("resolvido em", null=True, blank=True)

    class Meta:
        verbose_name = "chamado de suporte"
        verbose_name_plural = "chamados de suporte"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["rede", "situacao"])]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.get_situacao_display()})"

    @property
    def esta_aberto(self) -> bool:
        return self.situacao in {
            self.Situacao.ABERTO,
            self.Situacao.EM_ANDAMENTO,
            self.Situacao.AGUARDANDO,
        }


class MensagemDoChamado(models.Model):
    """Cada resposta do chamado, com autor e hora."""

    chamado = models.ForeignKey(
        ChamadoDeSuporte, on_delete=models.CASCADE, related_name="mensagens"
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mensagens_de_chamado",
    )
    texto = models.TextField("texto")
    interna = models.BooleanField("nota interna (nao aparece para o solicitante)", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "mensagem do chamado"
        verbose_name_plural = "mensagens do chamado"
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return f"{self.autor} em {self.criado_em:%d/%m %H:%M}"
