"""Modelos de integracao da API: webhooks de saida e tarefas assincronas (fase 7).

Ficam aqui e sao importados no fim de ``api/models.py`` para nao reescrever o
arquivo legado do app.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models


class WebhookDeSaida(models.Model):
    """Assinatura de evento para o cliente/integrador (RF-API-001/002/003)."""

    class Estado(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        PAUSADO = "pausado", "Pausado"

    rede = models.ForeignKey("core.Rede", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="webhooks", verbose_name="rede",
                             help_text="Em branco = webhook da plataforma.")
    url = models.URLField("endereco", max_length=500)
    eventos = models.JSONField("eventos assinados", default=list, blank=True,
                               help_text="Lista de eventos (RF-API-001). Vazio = todos.")
    segredo = models.CharField("segredo HMAC", max_length=80)
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.ATIVO)
    descricao = models.CharField("descricao", max_length=160, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "webhook de saida"
        verbose_name_plural = "webhooks de saida"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.url} ({len(self.eventos or []) or 'todos'} evento(s))"

    def assina(self, corpo: bytes, momento: int) -> str:
        mensagem = f"{momento}.".encode("ascii") + corpo
        return hmac.new(self.segredo.encode("utf-8"), mensagem, hashlib.sha256).hexdigest()

    def escuta(self, evento: str) -> bool:
        return not self.eventos or evento in self.eventos

    @classmethod
    def gerar_segredo(cls) -> str:
        return secrets.token_urlsafe(32)


class EntregaDeWebhook(models.Model):
    """Cada tentativa de entrega, com resposta e proxima retentativa (RF-API-002)."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ENTREGUE = "entregue", "Entregue"
        FALHOU = "falhou", "Falhou"
        DESISTIU = "desistiu", "Desistiu"

    webhook = models.ForeignKey(WebhookDeSaida, on_delete=models.CASCADE, related_name="entregas",
                                verbose_name="webhook")
    evento = models.CharField("evento", max_length=60)
    entrega = models.CharField("identificador da entrega", max_length=40, unique=True)
    payload = models.JSONField("corpo enviado", default=dict)
    situacao = models.CharField("situacao", max_length=10, choices=Situacao.choices,
                                default=Situacao.PENDENTE)
    tentativas = models.PositiveSmallIntegerField("tentativas", default=0)
    resposta = models.CharField("resposta", max_length=200, blank=True)
    proxima_tentativa = models.DateTimeField("proxima tentativa", null=True, blank=True)
    entregue_em = models.DateTimeField("entregue em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entrega de webhook"
        verbose_name_plural = "entregas de webhook"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.evento} -> {self.webhook_id} ({self.situacao})"

    @property
    def pode_retentar(self) -> bool:
        from api.webhooks import INTERVALOS

        return self.situacao != self.Situacao.ENTREGUE and self.tentativas < len(INTERVALOS)


class TarefaAssincrona(models.Model):
    """Job assincrono: relatorio, importacao, exportacao ou LGPD (RF-API-012/015)."""

    class Tipo(models.TextChoices):
        RELATORIO = "relatorio", "Relatorio"
        IMPORTACAO = "importacao", "Importacao"
        EXPORTACAO = "exportacao", "Exportacao"
        LGPD = "lgpd", "LGPD"

    class Situacao(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        RODANDO = "rodando", "Rodando"
        CONCLUIDA = "concluida", "Concluida"
        FALHOU = "falhou", "Falhou"

    rede = models.ForeignKey("core.Rede", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="tarefas", verbose_name="rede")
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    parametros = models.JSONField("parametros", default=dict, blank=True)
    situacao = models.CharField("situacao", max_length=10, choices=Situacao.choices,
                                default=Situacao.NA_FILA)
    progresso = models.PositiveSmallIntegerField("progresso (%)", default=0)
    resultado = models.JSONField("resultado", default=dict, blank=True)
    arquivo = models.CharField("arquivo gerado", max_length=400, blank=True)
    erro = models.TextField("erro", blank=True)
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="tarefas_pedidas",
                                       verbose_name="solicitado por")
    token = models.ForeignKey("api.ApiToken", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="tarefas", verbose_name="token")
    termina_em = models.DateTimeField("link expira em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "tarefa assincrona"
        verbose_name_plural = "tarefas assincronas"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} #{self.pk} ({self.get_situacao_display()})"
