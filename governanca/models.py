"""Governanca: observabilidade, backup, LGPD, 2FA e retencao (Fase 5 do PRD).

As entidades de plataforma/tenant que endurecem a operacao. Todas referenciam a
``Rede`` (ou o usuario) explicitamente -- nao usam o manager escopado, porque a
maioria delas e consultada de fora do contexto de um cliente (suporte, metricas,
alertas de backup).
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Rede


class RegraRetencao(models.Model):
    """Retencao e expurgo por entidade (LGPD/RNF-006, PRD 12)."""

    class Acao(models.TextChoices):
        ANONIMIZAR = "anonimizar", "Anonimizar"
        ELIMINAR = "eliminar", "Eliminar"
        CONSERVAR = "conservar", "Conservar (base legal)"

    entidade = models.CharField("entidade", max_length=60, unique=True)
    descricao = models.CharField("descricao", max_length=200, blank=True)
    prazo_dias = models.PositiveIntegerField("prazo (dias)", default=365)
    base_legal = models.CharField("base legal", max_length=200, blank=True)
    acao = models.CharField("acao", max_length=20, choices=Acao.choices, default=Acao.ANONIMIZAR)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "regra de retencao"
        verbose_name_plural = "regras de retencao"
        ordering = ["entidade"]

    def __str__(self) -> str:
        return f"{self.entidade} ({self.prazo_dias}d)"

    @property
    def base_legal_efetiva(self) -> str:
        return self.base_legal or "Obrigacao legal / execucao de contrato"


class MetricaTenant(models.Model):
    """Uso e erros por cliente, por hora (RNF-008)."""

    rede = models.ForeignKey(
        Rede,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="metricas",
        verbose_name="rede",
    )
    inicio = models.DateTimeField("hora")
    requisicoes = models.PositiveIntegerField("requisicoes", default=0)
    erros_5xx = models.PositiveIntegerField("erros 5xx", default=0)
    erros_4xx = models.PositiveIntegerField("erros 4xx", default=0)
    tempo_total_ms = models.BigIntegerField("tempo total (ms)", default=0)
    tempo_max_ms = models.PositiveIntegerField("pior tempo (ms)", default=0)

    class Meta:
        verbose_name = "metrica por cliente"
        verbose_name_plural = "metricas por cliente"
        ordering = ["-inicio"]
        constraints = [
            models.UniqueConstraint(fields=["rede", "inicio"], name="metrica_unica_por_hora"),
        ]

    def __str__(self) -> str:
        return f"{self.rede or 'sem rede'} @ {self.inicio:%d/%m %H:%M}"

    @property
    def tempo_medio_ms(self) -> int:
        return int(self.tempo_total_ms / self.requisicoes) if self.requisicoes else 0


class ErroTenant(models.Model):
    """Erro 5xx observado num cliente, para suporte e alerta (RNF-008)."""

    rede = models.ForeignKey(
        Rede,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="erros",
        verbose_name="rede",
    )
    rota = models.CharField("rota", max_length=200)
    metodo = models.CharField("metodo", max_length=10, blank=True)
    status = models.PositiveSmallIntegerField("status HTTP", default=500)
    tipo = models.CharField("tipo", max_length=120, blank=True)
    mensagem = models.TextField("mensagem", blank=True)
    traceback_curto = models.TextField("trecho do traceback", blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="erros_tenant",
        verbose_name="usuario",
    )
    resolvido = models.BooleanField("resolvido", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "erro por cliente"
        verbose_name_plural = "erros por cliente"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.status} {self.rota}"


class RegistroBackup(models.Model):
    """Execucao de backup e a verificacao por restauracao de teste (RNF-005)."""

    class Tipo(models.TextChoices):
        BANCO = "banco", "Banco de dados"
        MIDIA = "midia", "Midia"
        TENANT = "tenant", "Exportacao de um cliente"

    class Situacao(models.TextChoices):
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        OK = "ok", "Concluido"
        FALHOU = "falhou", "Falhou"

    arquivo = models.CharField("arquivo", max_length=300)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices, default=Tipo.BANCO)
    tamanho_bytes = models.BigIntegerField("tamanho (bytes)", default=0)
    sha256 = models.CharField("sha256", max_length=64, blank=True)
    rede = models.ForeignKey(
        Rede,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backups",
        verbose_name="rede",
    )
    situacao = models.CharField(
        "situacao", max_length=20, choices=Situacao.choices, default=Situacao.EM_ANDAMENTO
    )
    verificado_em = models.DateTimeField("verificado em", null=True, blank=True)
    verificacao = models.TextField("resultado da verificacao", blank=True)
    retencao_ate = models.DateField("reter ate", null=True, blank=True)
    erro = models.TextField("erro", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "registro de backup"
        verbose_name_plural = "registros de backup"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} {self.arquivo}"

    @property
    def verificado(self) -> bool:
        return self.verificado_em is not None

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho_bytes / 1_048_576, 2)


class SolicitacaoTitular(models.Model):
    """Pedido de titular de dados (LGPD art. 18) com prazo e desfecho."""

    class Tipo(models.TextChoices):
        ACESSO = "acesso", "Acesso aos dados"
        EXPORTACAO = "exportacao", "Exportacao"
        CORRECAO = "correcao", "Correcao"
        ELIMINACAO = "eliminacao", "Eliminacao/anonimizacao"

    class Situacao(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        CONCLUIDA = "concluida", "Concluida"
        RECUSADA = "recusada", "Recusada"

    PRAZO_LEGAL_DIAS = 15

    rede = models.ForeignKey(
        Rede, on_delete=models.CASCADE, related_name="solicitacoes_titular", verbose_name="rede"
    )
    titular_nome = models.CharField("titular", max_length=150)
    titular_email = models.CharField("e-mail do titular", max_length=200, blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=Tipo.choices)
    situacao = models.CharField(
        "situacao", max_length=20, choices=Situacao.choices, default=Situacao.ABERTA
    )
    prazo_em = models.DateField("prazo legal")
    descricao = models.TextField("descricao", blank=True)
    resposta = models.TextField("resposta ao titular", blank=True)
    concluida_em = models.DateTimeField("concluida em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "solicitacao de titular"
        verbose_name_plural = "solicitacoes de titular"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} - {self.titular_nome}"

    @property
    def atrasada(self) -> bool:
        return self.situacao == self.Situacao.ABERTA and self.prazo_em < timezone.localdate()

    @property
    def dias_restantes(self) -> int:
        return (self.prazo_em - timezone.localdate()).days


class AcessoDadoSensivel(models.Model):
    """Registro de leitura de dado sensivel -- ficha de saude (LGPD art. 11)."""

    class Origem(models.TextChoices):
        PAINEL = "painel", "Painel"
        API = "api", "API"
        SUPORTE = "suporte", "Suporte"
        IMPRESSAO = "impressao", "Impressao/PDF"

    rede = models.ForeignKey(
        Rede, on_delete=models.CASCADE, related_name="acessos_sensiveis", verbose_name="rede"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acessos_sensiveis",
        verbose_name="usuario",
    )
    titular_nome = models.CharField("titular", max_length=150)
    usuario_id_titular = models.PositiveIntegerField("id do cadastro", null=True, blank=True)
    recurso = models.CharField("recurso", max_length=60, default="ficha_saude")
    acao = models.CharField("acao", max_length=30, default="leitura")
    origem = models.CharField(
        "origem", max_length=20, choices=Origem.choices, default=Origem.PAINEL
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "acesso a dado sensivel"
        verbose_name_plural = "acessos a dado sensivel"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.acao} {self.recurso} - {self.titular_nome}"


class TentativaDeLogin(models.Model):
    """Historico de tentativas de acesso (RNF-009): rate limit e auditoria."""

    identificador = models.CharField("identificador", max_length=200, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    sucesso = models.BooleanField("sucesso", default=False)
    bloqueado = models.BooleanField("bloqueado", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tentativa de login"
        verbose_name_plural = "tentativas de login"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["identificador", "criado_em"]),
            models.Index(fields=["ip", "criado_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.identificador} ({'ok' if self.sucesso else 'falha'})"


class Dispositivo2FA(models.Model):
    """Segundo fator (TOTP) do usuario (RNF-009)."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dois_fatores",
        verbose_name="usuario",
    )
    segredo = models.CharField("segredo", max_length=64)
    confirmado_em = models.DateTimeField("confirmado em", null=True, blank=True)
    ultimo_uso_em = models.DateTimeField("ultimo uso em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "dispositivo 2FA"
        verbose_name_plural = "dispositivos 2FA"

    def __str__(self) -> str:
        return f"2FA de {self.usuario}"

    @property
    def ativo(self) -> bool:
        return self.confirmado_em is not None


class CodigoRecuperacao(models.Model):
    """Codigo de recuperacao do 2FA: hash, uso unico."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacao",
        verbose_name="usuario",
    )
    hash_codigo = models.CharField("hash", max_length=128)
    usado_em = models.DateTimeField("usado em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "codigo de recuperacao"
        verbose_name_plural = "codigos de recuperacao"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"codigo de {self.usuario}"

    @staticmethod
    def gerar_hash(codigo: str) -> str:
        chave = (getattr(settings, "SECRET_KEY", "") or "sem-chave").encode()
        return hashlib.pbkdf2_hmac("sha256", codigo.encode(), chave, 100_000).hex()


class RotinaAgendada(models.Model):
    """Rotina periodica com o resultado da ultima execucao (fase 6/7: jobs)."""

    class Periodicidade(models.TextChoices):
        HORA = "hora", "De hora em hora"
        DIA = "dia", "Diaria"
        SEMANA = "semana", "Semanal"
        MES = "mes", "Mensal"

    class Situacao(models.TextChoices):
        OK = "ok", "Concluida"
        FALHOU = "falhou", "Falhou"
        PULADA = "pulada", "Pulada"

    nome = models.CharField("nome", max_length=60, unique=True)
    descricao = models.CharField("descricao", max_length=200, blank=True)
    periodicidade = models.CharField(
        "periodicidade", max_length=10, choices=Periodicidade.choices, default=Periodicidade.DIA
    )
    ativa = models.BooleanField("ativa", default=True)
    executa_dry_run = models.BooleanField(
        "executa em modo simulacao", default=False, help_text="Roda a rotina sem gravar nada."
    )
    ultima_execucao = models.DateTimeField("ultima execucao", null=True, blank=True)
    ultima_situacao = models.CharField(
        "situacao da ultima execucao", max_length=10, choices=Situacao.choices, blank=True
    )
    ultimo_resultado = models.TextField("resultado da ultima execucao", blank=True)
    duracao_ms = models.PositiveIntegerField("duracao (ms)", default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "rotina agendada"
        verbose_name_plural = "rotinas agendadas"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @property
    def atrasada(self) -> bool:
        if self.ultima_execucao is None:
            return True
        limites = {
            "hora": timedelta(hours=2),
            "dia": timedelta(days=1, hours=2),
            "semana": timedelta(days=8),
            "mes": timedelta(days=32),
        }
        return timezone.now() - self.ultima_execucao > limites.get(
            self.periodicidade, timedelta(days=2)
        )
