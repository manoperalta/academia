"""Modelos de tenancy: Rede (tenant), Unidade (escopo) e VinculoUsuario (RBAC)."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.managers import SemEscopoManager, TenantManager
from core.papeis import Papel, StatusRede, StatusUnidade, TipoUnidade


class Rede(models.Model):
    """A academia cliente: o tenant (dono dos dados, do contrato e do pagamento).

    ``slug`` identifica a rede na URL (``/a/<slug>/``) e no subdominio.
    """

    nome = models.CharField("nome", max_length=150)
    slug = models.SlugField("slug", max_length=60, unique=True)
    cnpj = models.CharField("CNPJ", max_length=20, blank=True)
    email_responsavel = models.EmailField("e-mail do responsavel", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    dominio = models.CharField("dominio proprio", max_length=253, blank=True)
    status = models.CharField(
        "status", max_length=20, choices=StatusRede.choices, default=StatusRede.ATIVO
    )
    trial_termina_em = models.DateTimeField("teste termina em", null=True, blank=True)
    observacoes_internas = models.TextField("observacoes internas", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    objects = SemEscopoManager()
    todos = SemEscopoManager()

    class Meta:
        verbose_name = "rede"
        verbose_name_plural = "redes"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome

    @property
    def esta_ativa(self) -> bool:
        return self.status in {StatusRede.ATIVO, StatusRede.TRIAL}

    @property
    def permite_escrita(self) -> bool:
        """Bloqueio de escrita por inadimplencia (PRD 11.2)."""
        return self.status in {StatusRede.ATIVO, StatusRede.TRIAL, StatusRede.INADIMPLENTE}


class Unidade(models.Model):
    """Estabelecimento dentro da rede (propria, franqueada ou licenciada)."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="unidades")
    nome = models.CharField("nome", max_length=150)
    codigo = models.CharField("codigo", max_length=30, blank=True)
    tipo = models.CharField(
        "tipo", max_length=20, choices=TipoUnidade.choices, default=TipoUnidade.MATRIZ
    )
    cnpj = models.CharField("CNPJ", max_length=20, blank=True)
    endereco = models.CharField("endereco", max_length=255, blank=True)
    cidade = models.CharField("cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    gestor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unidades_geridas",
        verbose_name="gestor responsavel",
    )
    status = models.CharField(
        "status", max_length=20, choices=StatusUnidade.choices, default=StatusUnidade.ATIVA
    )
    sobrescrever_branding = models.BooleanField("pode sobrescrever a marca", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    objects = SemEscopoManager()
    todos = SemEscopoManager()

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        ordering = ["rede", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["rede", "codigo"],
                condition=~models.Q(codigo=""),
                name="unidade_codigo_unico_por_rede",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.rede.slug})" if self.rede_id else self.nome

    @property
    def esta_ativa(self) -> bool:
        return self.status == StatusUnidade.ATIVA


class VinculoUsuario(models.Model):
    """Liga um usuario a uma rede (e opcionalmente a uma unidade) com um papel.

    ``unidade=None`` significa "vale para toda a rede" -- e o caso de
    administrador da rede, financeiro e auditor.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vinculos"
    )
    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="vinculos")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.CASCADE, null=True, blank=True, related_name="vinculos"
    )
    papel = models.CharField("papel", max_length=30, choices=Papel.choices)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    objects = SemEscopoManager()
    todos = SemEscopoManager()

    class Meta:
        verbose_name = "vinculo de usuario"
        verbose_name_plural = "vinculos de usuario"
        ordering = ["rede", "usuario"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "rede", "unidade", "papel"],
                name="vinculo_unico_por_usuario_rede_unidade_papel",
            )
        ]

    def __str__(self) -> str:
        destino = self.unidade.nome if self.unidade_id else "rede inteira"
        return f"{self.usuario} - {self.get_papel_display()} ({destino})"

    def cobre_a_rede(self) -> bool:
        return self.unidade_id is None


class TenantModel(models.Model):
    """Base abstrata para todo dado que pertence a uma rede (e opcionalmente a uma unidade).

    Transicao consciente: ``rede`` e ``unidade`` sao anulaveis para que a base
    atual continue funcionando enquanto as telas sao convertidas; o preenchimento
    automatico vem do contexto (middleware). O passo final -- tornar ``rede``
    obrigatoria -- esta previsto no PRD (secao 17, migracao aditiva) e nao deve
    ser feito antes de todas as telas gravarem com contexto.
    """

    rede = models.ForeignKey(
        Rede,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name="rede",
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name="unidade",
    )
    arquivado_em = models.DateTimeField("arquivado em", null=True, blank=True, db_index=True)

    objects = TenantManager()
    todos = SemEscopoManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from core.context import rede_atual, unidade_atual

        if self.rede_id is None:
            rede = rede_atual()
            if rede is not None and rede.pk is not None:
                self.rede_id = rede.pk
        if self.unidade_id is None:
            unidade = unidade_atual()
            if unidade is not None and unidade.pk is not None:
                self.unidade_id = unidade.pk
        return super().save(*args, **kwargs)

    def arquivar(self, salvar: bool = True):
        """Arquivamento (soft delete). Nunca apaga dado de negocio."""
        self.arquivado_em = timezone.now()
        if salvar:
            self.save(update_fields=["arquivado_em"])
        return self

    def restaurar(self, salvar: bool = True):
        self.arquivado_em = None
        if salvar:
            self.save(update_fields=["arquivado_em"])
        return self

    @property
    def arquivado(self) -> bool:
        return self.arquivado_em is not None


class UnidadeModel(TenantModel):
    """Base abstrata para dado que sempre nasce dentro de uma unidade."""

    class Meta:
        abstract = True


class ConviteEquipe(models.Model):
    """Convite para alguem entrar na equipe de uma rede (opcionalmente de uma unidade)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ACEITO = "aceito", "Aceito"
        EXPIRADO = "expirado", "Expirado"
        CANCELADO = "cancelado", "Cancelado"

    rede = models.ForeignKey(
        "core.Rede", on_delete=models.CASCADE, related_name="convites", verbose_name="rede"
    )
    unidade = models.ForeignKey(
        "core.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="convites",
        verbose_name="unidade",
    )
    email = models.EmailField("e-mail")
    papel = models.CharField("papel", max_length=32, choices=Papel.choices)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDENTE, db_index=True
    )
    expira_em = models.DateTimeField("expira em")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="convites_criados",
        verbose_name="criado por",
    )
    criado_em = models.DateTimeField(default=timezone.now)
    aceito_em = models.DateTimeField(null=True, blank=True)
    aceito_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="convites_aceitos",
        verbose_name="aceito por",
    )

    class Meta:
        verbose_name = "convite de equipe"
        verbose_name_plural = "convites de equipe"
        ordering = ("-criado_em",)

    def __str__(self) -> str:
        return f"{self.email} ({self.get_papel_display()})"

    @staticmethod
    def gerar_token() -> str:
        return secrets.token_urlsafe(32)

    @property
    def expirado(self) -> bool:
        return bool(self.expira_em and self.expira_em < timezone.now())

    def esta_valido(self) -> bool:
        return self.status == self.Status.PENDENTE and not self.expirado

    def aceitar(self, usuario):
        """Cria (ou ajusta) o vinculo do usuario e marca o convite como aceito."""
        vinculo, _ = VinculoUsuario.objects.get_or_create(
            usuario=usuario,
            rede=self.rede,
            unidade=self.unidade,
            defaults={"papel": self.papel, "ativo": True},
        )
        if vinculo.papel != self.papel or not vinculo.ativo:
            vinculo.papel = self.papel
            vinculo.ativo = True
            vinculo.save(update_fields=["papel", "ativo"])
        self.status = self.Status.ACEITO
        self.aceito_em = timezone.now()
        self.aceito_por = usuario
        self.save(update_fields=["status", "aceito_em", "aceito_por"])
        return vinculo
