"""Modelos da API: token de servico e trilha de auditoria."""

from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Rede, Unidade


class ApiToken(models.Model):
    """Token de servico para automacao (Hermes, integracoes do cliente).

    O segredo so existe em claro no momento da criacao: guardamos apenas o hash.
    Formato da credencial: ``<prefixo>.<segredo>``.
    """

    PREFIXO_TAMANHO = 12

    nome = models.CharField("nome", max_length=100, help_text="Para que este token serve")
    prefixo = models.CharField("prefixo", max_length=20, unique=True, editable=False)
    hash_segredo = models.CharField("hash do segredo", max_length=128, editable=False)
    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="tokens")
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tokens",
        help_text="Vazio = token vale para todas as unidades da rede",
    )
    escopos = models.JSONField("escopos", default=list)
    ativo = models.BooleanField("ativo", default=True)
    expira_em = models.DateTimeField("expira em", null=True, blank=True)
    ultimo_uso_em = models.DateTimeField("ultimo uso em", null=True, blank=True)
    ultimo_ip = models.GenericIPAddressField("ultimo IP", null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tokens_criados",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    revogado_em = models.DateTimeField("revogado em", null=True, blank=True)

    class Meta:
        verbose_name = "token de API"
        verbose_name_plural = "tokens de API"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.prefixo}...)"

    # -- ciclo de vida -----------------------------------------------------
    @classmethod
    def gerar(cls, **campos):
        """Cria um token e devolve ``(token, segredo_em_claro)``."""
        segredo = secrets.token_urlsafe(32)
        prefixo = secrets.token_hex(cls.PREFIXO_TAMANHO // 2)
        campos.setdefault("escopos", [])
        token = cls(prefixo=prefixo, hash_segredo=cls.hash_de(segredo), **campos)
        token.save()
        return token, f"{prefixo}.{segredo}"

    def rotacionar(self):
        """Troca o segredo mantendo o mesmo token (devolve o novo em claro)."""
        segredo = secrets.token_urlsafe(32)
        self.hash_segredo = self.hash_de(segredo)
        self.save(update_fields=["hash_segredo"])
        return f"{self.prefixo}.{segredo}"

    @staticmethod
    def hash_de(segredo: str) -> str:
        return hashlib.sha256(segredo.encode()).hexdigest()

    @classmethod
    def por_credencial(cls, credencial: str):
        """Localiza o token a partir de ``<prefixo>.<segredo>`` (ou ``None``)."""
        if not credencial or "." not in credencial:
            return None
        prefixo, segredo = credencial.split(".", 1)
        token = cls.objects.select_related("rede", "unidade").filter(prefixo=prefixo).first()
        if token is None:
            return None
        if not secrets.compare_digest(token.hash_segredo, cls.hash_de(segredo)):
            return None
        return token

    def esta_valido(self) -> bool:
        if not self.ativo or self.revogado_em is not None:
            return False
        return not (self.expira_em and self.expira_em < timezone.now())

    def marcar_uso(self, ip=None):
        self.ultimo_uso_em = timezone.now()
        if ip:
            self.ultimo_ip = ip
        self.save(update_fields=["ultimo_uso_em", "ultimo_ip"])


class RegistroAuditoria(models.Model):
    """Trilha append-only do que aconteceu no sistema (RNF-007).

    Nunca e editado nem apagado pela aplicacao: e o que sustenta a resposta a
    "quem fez o que, quando e em qual rede".
    """

    class Acao(models.TextChoices):
        CRIAR = "criar", "Criar"
        ALTERAR = "alterar", "Alterar"
        ARQUIVAR = "arquivar", "Arquivar"
        RESTAURAR = "restaurar", "Restaurar"
        EXPORTAR = "exportar", "Exportar"
        IMPORTAR = "importar", "Importar"
        LOGIN = "login", "Entrar"
        IMPERSONAR = "impersonar", "Acesso de suporte"
        API = "api", "Chamada de API"

    rede = models.ForeignKey(
        Rede, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditoria"
    )
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditoria"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditoria",
    )
    token = models.ForeignKey(
        ApiToken, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditoria"
    )
    acao = models.CharField("acao", max_length=20, choices=Acao.choices)
    entidade = models.CharField("entidade", max_length=80)
    entidade_id = models.CharField("id da entidade", max_length=64, blank=True)
    descricao = models.CharField("descricao", max_length=255, blank=True)
    dados_antes = models.JSONField("antes", null=True, blank=True)
    dados_depois = models.JSONField("depois", null=True, blank=True)
    pedido_origem = models.TextField("pedido de origem", blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    request_id = models.CharField("request id", max_length=64, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["rede", "-criado_em"]),
            models.Index(fields=["entidade", "entidade_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.criado_em:%d/%m/%Y %H:%M} {self.acao} {self.entidade}"

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValueError("Registro de auditoria nao pode ser alterado (append-only).")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Registro de auditoria nao pode ser apagado (append-only).")
