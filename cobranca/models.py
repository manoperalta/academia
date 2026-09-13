"""Modelos da cobranca recorrente (Pix automatico e cartao recorrente).

A ideia e tirar a mensalidade da mao do aluno: ele autoriza o debito uma vez, a rede gera a cobranca
todo mes e o retorno do banco vira pagamento sozinho. Tudo com **um registro por evento**, porque
cobranca e o lugar onde "o sistema diz que pagou e o banco diz que nao" precisa de prova.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede, Unidade


class AutorizacaoDeDebito(models.Model):
    """Mandato do aluno para debitar a mensalidade automaticamente."""

    class Modalidade(models.TextChoices):
        PIX_AUTOMATICO = "pix_automatico", "Pix automatico"
        CARTAO_RECORRENTE = "cartao_recorrente", "Cartao recorrente"

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente de confirmacao"
        ATIVA = "ativa", "Ativa"
        SUSPENSA = "suspensa", "Suspensa"
        CANCELADA = "cancelada", "Cancelada"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="autorizacoes_de_debito")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="autorizacoes_de_debito",
        verbose_name="aluno",
    )
    modalidade = models.CharField(
        "modalidade", max_length=20, choices=Modalidade.choices, default=Modalidade.PIX_AUTOMATICO
    )
    chave_pix = models.CharField("chave Pix do pagador", max_length=120, blank=True)
    limite_por_cobranca = models.DecimalField(
        "limite por cobranca", max_digits=10, decimal_places=2, default=0
    )
    situacao = models.CharField(
        "situacao", max_length=12, choices=Situacao.choices, default=Situacao.PENDENTE
    )
    identificador_no_banco = models.CharField("identificador no banco", max_length=80, blank=True)
    autorizada_em = models.DateTimeField("autorizada em", null=True, blank=True)
    cancelada_em = models.DateTimeField("cancelada em", null=True, blank=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="autorizacoes_criadas",
    )
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "autorizacao de debito"
        verbose_name_plural = "autorizacoes de debito"
        ordering = ["-criada_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "modalidade"], name="autorizacao_unica_por_aluno_e_modalidade"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.get_modalidade_display()} ({self.get_situacao_display()})"

    @property
    def esta_ativa(self) -> bool:
        return self.situacao == self.Situacao.ATIVA


class CobrancaRecorrente(models.Model):
    """A mensalidade de um aluno em uma competencia, com o ciclo de vida da cobranca."""

    class Situacao(models.TextChoices):
        PREVISTA = "prevista", "Prevista"
        ENVIADA = "enviada", "Enviada ao banco"
        PAGA = "paga", "Paga"
        RECUSADA = "recusada", "Recusada"
        CANCELADA = "cancelada", "Cancelada"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="cobrancas")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="cobrancas"
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="cobrancas",
        verbose_name="aluno",
    )
    autorizacao = models.ForeignKey(
        AutorizacaoDeDebito,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cobrancas",
    )
    competencia = models.DateField("competencia (primeiro dia do mes)")
    valor = models.DecimalField("valor", max_digits=10, decimal_places=2, default=0)
    vencimento = models.DateField("vencimento")
    situacao = models.CharField(
        "situacao", max_length=10, choices=Situacao.choices, default=Situacao.PREVISTA
    )
    tentativas = models.PositiveSmallIntegerField("tentativas de envio", default=0)
    motivo_da_recusa = models.CharField("motivo da recusa", max_length=200, blank=True)
    identificador_no_banco = models.CharField("identificador no banco", max_length=80, blank=True)
    pagamento = models.ForeignKey(
        "financeiro.Pagamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cobrancas",
    )
    pago_em = models.DateTimeField("pago em", null=True, blank=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "cobranca recorrente"
        verbose_name_plural = "cobrancas recorrentes"
        ordering = ["vencimento", "aluno__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "competencia"], name="cobranca_unica_por_aluno_e_competencia"
            ),
        ]
        indexes = [models.Index(fields=["rede", "situacao"])]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.competencia:%m/%Y} — R$ {self.valor} ({self.get_situacao_display()})"

    @property
    def dias_de_atraso(self) -> int:
        from django.utils import timezone

        if self.situacao in {self.Situacao.PAGA, self.Situacao.CANCELADA}:
            return 0
        return max(0, (timezone.localdate() - self.vencimento).days)


class EventoDaCobranca(models.Model):
    """Cada evento do ciclo: envio, lembrete, retorno do banco. Nada de estado sem historico."""

    class Tipo(models.TextChoices):
        CRIADA = "criada", "Cobranca criada"
        LEMBRETE = "lembrete", "Lembrete enviado ao aluno"
        ENVIADA = "enviada", "Enviada ao banco"
        PAGA = "paga", "Pagamento confirmado"
        RECUSADA = "recusada", "Recusada pelo banco"
        DEVOLVIDA = "devolvida", "Devolvida ou estornada"
        CANCELADA = "cancelada", "Cancelada pela rede"

    cobranca = models.ForeignKey(
        CobrancaRecorrente, on_delete=models.CASCADE, related_name="eventos"
    )
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    detalhe = models.TextField("detalhe", blank=True)
    dados = models.JSONField("dados do retorno", default=dict, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "evento da cobranca"
        verbose_name_plural = "eventos da cobranca"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.cobranca_id}"
