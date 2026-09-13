"""Modelos da assinatura eletronica: envelope, signatarios e a trilha de assinatura.

Assinatura eletronica **simples**, com trilha de auditoria verificavel: cada assinatura guarda o
hash do documento, o hash da assinatura anterior e quem assinou. Isso permite provar *quem assinou o
que, quando e em que ordem* — e detectar alteracao posterior no documento.

Assinatura com certificado ICP-Brasil fica pendente (depende de certificado e contrato com a AC).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede


class EnvelopeDeAssinatura(models.Model):
    """Um documento a colher assinaturas (contrato de adesao, termo de saude e afins)."""

    class Tipo(models.TextChoices):
        CONTRATO = "contrato", "Contrato de adesao"
        TERMO_DE_SAUDE = "termo_de_saude", "Termo de saude"
        AUTORIZACAO_DE_IMAGEM = "autorizacao_de_imagem", "Autorizacao de imagem"
        DISTRATO = "distrato", "Distrato"

    class Situacao(models.TextChoices):
        AGUARDANDO = "aguardando", "Aguardando assinaturas"
        PARCIAL = "parcial", "Parcialmente assinado"
        ASSINADO = "assinado", "Assinado"
        RECUSADO = "recusado", "Recusado"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="envelopes")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envelopes",
        verbose_name="aluno",
    )
    tipo = models.CharField("tipo", max_length=25, choices=Tipo.choices, default=Tipo.CONTRATO)
    titulo = models.CharField("titulo", max_length=200)
    caminho_do_documento = models.CharField("caminho do documento", max_length=300, blank=True)
    hash_do_documento = models.CharField("hash do documento (sha256)", max_length=64, blank=True)
    situacao = models.CharField(
        "situacao", max_length=12, choices=Situacao.choices, default=Situacao.AGUARDANDO
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envelopes_criados",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    concluido_em = models.DateTimeField("concluido em", null=True, blank=True)

    class Meta:
        verbose_name = "envelope de assinatura"
        verbose_name_plural = "envelopes de assinatura"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.get_situacao_display()})"

    @property
    def assinaturas_ok(self) -> int:
        return self.signatarios.filter(situacao=Signatario.Situacao.ASSINOU).count()

    @property
    def total_de_signatarios(self) -> int:
        return self.signatarios.count()

    @property
    def pendentes(self):
        return self.signatarios.filter(situacao=Signatario.Situacao.PENDENTE)


class Signatario(models.Model):
    """Quem precisa assinar, na ordem definida."""

    class Papel(models.TextChoices):
        ALUNO = "aluno", "Aluno"
        RESPONSAVEL = "responsavel", "Responsavel legal"
        ACADEMIA = "academia", "Representante da academia"
        TESTEMUNHA = "testemunha", "Testemunha"

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ASSINOU = "assinou", "Assinou"
        RECUSOU = "recusou", "Recusou"

    envelope = models.ForeignKey(
        EnvelopeDeAssinatura, on_delete=models.CASCADE, related_name="signatarios"
    )
    nome = models.CharField("nome", max_length=150)
    papel = models.CharField("papel", max_length=15, choices=Papel.choices, default=Papel.ALUNO)
    email = models.EmailField("e-mail", blank=True)
    ordem = models.PositiveSmallIntegerField("ordem", default=1)
    situacao = models.CharField(
        "situacao", max_length=10, choices=Situacao.choices, default=Situacao.PENDENTE
    )
    assinou_em = models.DateTimeField("assinou em", null=True, blank=True)
    motivo_da_recusa = models.CharField("motivo da recusa", max_length=200, blank=True)

    class Meta:
        verbose_name = "signatario"
        verbose_name_plural = "signatarios"
        ordering = ["ordem", "pk"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_papel_display()})"


class Assinatura(models.Model):
    """A prova: hash do documento, hash do elo anterior e dados de contexto."""

    signatario = models.OneToOneField(
        Signatario, on_delete=models.CASCADE, related_name="assinatura"
    )
    tipo = models.CharField("tipo", max_length=25, default="eletronica_simples")
    hash_do_documento = models.CharField("hash do documento (sha256)", max_length=64)
    hash_anterior = models.CharField("hash do elo anterior", max_length=64, blank=True)
    hash_da_assinatura = models.CharField("hash desta assinatura", max_length=64)
    endereco_ip = models.CharField("endereco IP", max_length=45, blank=True)
    navegador = models.CharField("navegador", max_length=200, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "assinatura"
        verbose_name_plural = "assinaturas"
        ordering = ["criado_em"]

    def __str__(self) -> str:
        return f"Assinatura de {self.signatario.nome}"
