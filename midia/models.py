"""Modelos da midia: o arquivo (com estado de envio) e as partes recebidas.

Escolha de projeto: o envio e retomavel. Cada parte tem o proprio hash, entao uma conexao que cai
no meio nao obriga a subir o arquivo inteiro de novo — basta reenviar a parte que falhou. O
arquivo so vira "pronto" quando todas as partes chegam, o tamanho confere e o hash final bate com
o do arquivo original.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede, Unidade
from core.validadores import TAMANHO_MAXIMO_DE_IMAGEM, TAMANHO_MAXIMO_DE_VIDEO

TAMANHO_DA_PARTE = 4 * 1024 * 1024
TAMANHO_MAXIMO = 2 * 1024 * 1024 * 1024

#: Limite por tipo de midia. O video de aula para em 450 MB e a capa em 5 MB -- o teto
#: absoluto (``TAMANHO_MAXIMO``) existe para o que nao e video nem capa.
LIMITES_POR_TIPO = {
    "video": TAMANHO_MAXIMO_DE_VIDEO,
    "imagem": TAMANHO_MAXIMO_DE_IMAGEM,
    "audio": 60 * 1024 * 1024,
    "documento": 60 * 1024 * 1024,
}


class ArquivoDeMidia(models.Model):
    """Arquivo de midia de uma rede (video, imagem, audio ou documento)."""

    class Tipo(models.TextChoices):
        VIDEO = "video", "Video"
        IMAGEM = "imagem", "Imagem"
        AUDIO = "audio", "Audio"
        DOCUMENTO = "documento", "Documento"

    class Situacao(models.TextChoices):
        ENVIANDO = "enviando", "Enviando"
        PROCESSANDO = "processando", "Processando"
        PRONTO = "pronto", "Pronto"
        ERRO = "erro", "Erro"
        REMOVIDO = "removido", "Removido"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="midias")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="midias"
    )
    aula = models.ForeignKey(
        "aulas.Aulas",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias_enviadas",
    )
    titulo = models.CharField("titulo", max_length=200)
    nome_original = models.CharField("nome do arquivo", max_length=255, blank=True)
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices, default=Tipo.VIDEO)
    situacao = models.CharField(
        "situacao", max_length=12, choices=Situacao.choices, default=Situacao.ENVIANDO
    )
    mime = models.CharField("tipo de conteudo", max_length=120, blank=True)
    tamanho_previsto = models.BigIntegerField("tamanho previsto (bytes)", default=0)
    tamanho_bytes = models.BigIntegerField("tamanho gravado (bytes)", default=0)
    hash_esperado = models.CharField("hash esperado (sha256)", max_length=64, blank=True)
    hash_final = models.CharField("hash do arquivo (sha256)", max_length=64, blank=True)
    largura = models.PositiveIntegerField("largura (px)", null=True, blank=True)
    altura = models.PositiveIntegerField("altura (px)", null=True, blank=True)
    duracao_segundos = models.PositiveIntegerField("duracao (s)", null=True, blank=True)
    caminho = models.CharField("caminho no armazenamento", max_length=300, blank=True)
    publicado = models.BooleanField("visivel para o aluno", default=False)
    erro = models.CharField("ultimo erro", max_length=300, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias_enviadas",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    concluido_em = models.DateTimeField("concluido em", null=True, blank=True)
    processado_em = models.DateTimeField("processado em", null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "arquivo de midia"
        verbose_name_plural = "arquivos de midia"
        indexes = [
            models.Index(fields=["rede", "situacao"]),
            models.Index(fields=["rede", "tipo"]),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.get_situacao_display()})"

    @staticmethod
    def limite_do_tipo(tipo: str) -> int:
        """Teto de tamanho do tipo informado (video 450 MB, imagem 5 MB...)."""
        return min(LIMITES_POR_TIPO.get(tipo, TAMANHO_MAXIMO), TAMANHO_MAXIMO)

    # ------------------------------------------------------------- conveniencias
    @property
    def total_de_partes(self) -> int:
        if self.tamanho_previsto <= 0:
            return 0
        return (self.tamanho_previsto + TAMANHO_DA_PARTE - 1) // TAMANHO_DA_PARTE

    @property
    def partes_recebidas(self) -> int:
        return self.partes.count()

    @property
    def progresso(self) -> int:
        """Percentual concluido, calculado pelo tamanho das partes ja recebidas."""
        if self.situacao in {self.Situacao.PRONTO, self.Situacao.PROCESSANDO}:
            return 100
        if self.tamanho_previsto <= 0:
            return 0
        recebido = self.partes.aggregate(total=models.Sum("tamanho_bytes"))["total"] or 0
        return min(99, int(recebido * 100 / self.tamanho_previsto))

    @property
    def esta_pronto(self) -> bool:
        return self.situacao == self.Situacao.PRONTO

    @property
    def tamanho_legivel(self) -> str:
        return tamanho_legivel(self.tamanho_bytes or self.tamanho_previsto)

    def url_de_entrega(self, minutos: int = 15) -> str:
        """URL assinada e temporaria do arquivo (nunca o caminho cru)."""
        from midia import servicos

        return servicos.url_de_entrega(self, minutos=minutos)


class ParteDeMidia(models.Model):
    """Uma parte do envio, com hash proprio para conferir a integridade."""

    arquivo = models.ForeignKey(ArquivoDeMidia, on_delete=models.CASCADE, related_name="partes")
    numero = models.PositiveIntegerField("numero da parte")
    tamanho_bytes = models.BigIntegerField("tamanho (bytes)", default=0)
    hash_da_parte = models.CharField("hash da parte (sha256)", max_length=64, blank=True)
    recebida_em = models.DateTimeField("recebida em", auto_now_add=True)

    class Meta:
        ordering = ["numero"]
        verbose_name = "parte de envio"
        verbose_name_plural = "partes de envio"
        constraints = [
            models.UniqueConstraint(fields=["arquivo", "numero"], name="midia_parte_unica"),
        ]

    def __str__(self) -> str:
        return f"parte {self.numero} de {self.arquivo_id}"


def tamanho_legivel(bytes_: int | None) -> str:
    if not bytes_:
        return "0 B"
    unidades = ("B", "KB", "MB", "GB")
    valor = float(bytes_)
    for unidade in unidades:
        if valor < 1024 or unidade == unidades[-1]:
            return f"{valor:.0f} {unidade}" if unidade == "B" else f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} GB"
