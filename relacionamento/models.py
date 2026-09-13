"""Modelos de relacionamento: o funil de captacao e o risco de evasao do aluno.

Duas ideias guiam este app:

* **Lead nao e aluno** — guarda a origem, o interesse e cada conversa, para a rede saber qual canal
  traz matricula que fica, e nao apenas matricula.
* **Risco de evasao e explicado, nao adivinhado** — cada ponto do score vem de um sinal real
  (dias sem treinar, mensalidade vencida, nota de detrator) e a tela mostra a conta, como na memoria
  de calculo do repasse.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede, Unidade


class OrigemDoLead(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    INDICACAO = "indicacao", "Indicacao de aluno"
    PORTA = "porta", "Passou na porta"
    SITE = "site", "Site ou landing"
    WHATSAPP = "whatsapp", "WhatsApp"
    GOOGLE = "google", "Busca no Google"
    PARCEIRO = "parceiro", "Parceiro ou empresa"
    OUTRO = "outro", "Outro"


class Lead(models.Model):
    """Interessado que ainda nao e aluno, com o historico de contato."""

    class Situacao(models.TextChoices):
        NOVO = "novo", "Novo"
        CONTATADO = "contatado", "Contatado"
        VISITA_AGENDADA = "visita_agendada", "Visita agendada"
        VISITOU = "visitou", "Visitou"
        MATRICULADO = "matriculado", "Matriculado"
        PERDIDO = "perdido", "Perdido"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="leads")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    nome = models.CharField("nome", max_length=150)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    origem = models.CharField(
        "origem", max_length=20, choices=OrigemDoLead.choices, default=OrigemDoLead.OUTRO
    )
    interesse = models.CharField("interesse", max_length=150, blank=True)
    valor_estimado = models.DecimalField(
        "valor mensal estimado", max_digits=10, decimal_places=2, default=0
    )
    situacao = models.CharField(
        "situacao", max_length=20, choices=Situacao.choices, default=Situacao.NOVO
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_sob_responsabilidade",
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="origem_como_lead",
        verbose_name="aluno gerado",
    )
    motivo_da_perda = models.CharField("motivo da perda", max_length=200, blank=True)
    observacoes = models.TextField("observacoes", blank=True)
    proximo_contato_em = models.DateField("proximo contato", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    convertido_em = models.DateTimeField("convertido em", null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "lead"
        verbose_name_plural = "leads"
        indexes = [
            models.Index(fields=["rede", "situacao"]),
            models.Index(fields=["rede", "origem"]),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_situacao_display()})"

    @property
    def esta_aberto(self) -> bool:
        return self.situacao not in {self.Situacao.MATRICULADO, self.Situacao.PERDIDO}

    @property
    def dias_ate_matricular(self) -> int | None:
        if not self.convertido_em:
            return None
        return (self.convertido_em - self.criado_em).days


class InteracaoComLead(models.Model):
    """Cada contato feito: o que foi conversado e quando falar de novo."""

    class Tipo(models.TextChoices):
        LIGACAO = "ligacao", "Ligacao"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"
        VISITA = "visita", "Visita a unidade"
        PRESENCIAL = "presencial", "Atendimento presencial"
        OUTRO = "outro", "Outro"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interacoes")
    tipo = models.CharField("tipo", max_length=15, choices=Tipo.choices, default=Tipo.WHATSAPP)
    resumo = models.TextField("resumo")
    resultado = models.CharField("resultado", max_length=200, blank=True)
    feito_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interacoes_de_lead",
    )
    proximo_contato_em = models.DateField("proximo contato", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "interacao com lead"
        verbose_name_plural = "interacoes com lead"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} em {self.criado_em:%d/%m/%Y}"


class PerfilDeRisco(models.Model):
    """Risco de evasao do aluno, com os sinais que produziram a pontuacao."""

    class Faixa(models.TextChoices):
        BAIXO = "baixo", "Baixo"
        MEDIO = "medio", "Medio"
        ALTO = "alto", "Alto"
        CRITICO = "critico", "Critico"

    class Acao(models.TextChoices):
        NENHUMA = "nenhuma", "Nenhuma acao"
        CONVITE_AVALIACAO = "convite_avaliacao", "Convidar para avaliacao fisica"
        CONTATO_WHATSAPP = "contato_whatsapp", "Falar no WhatsApp"
        LIGACAO = "ligacao", "Ligar"
        OFERTA_RETENCAO = "oferta_retencao", "Oferta de retencao"
        TRANSFERENCIA = "transferencia", "Oferecer troca de unidade ou horario"

    class Desfecho(models.TextChoices):
        EM_ABERTO = "em_aberto", "Em aberto"
        RECUPERADO = "recuperado", "Recuperado (voltou a treinar)"
        CONTINUOU_AUSENTE = "continuou_ausente", "Continuou ausente"
        CANCELOU = "cancelou", "Cancelou"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="perfis_de_risco")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="perfis_de_risco",
        verbose_name="aluno",
    )
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="perfis_de_risco"
    )
    pontuacao = models.PositiveSmallIntegerField("pontuacao (0-100)", default=0)
    faixa = models.CharField("faixa", max_length=10, choices=Faixa.choices, default=Faixa.BAIXO)
    motivos = models.JSONField("motivos", default=list, blank=True)
    dias_sem_treinar = models.PositiveIntegerField("dias sem treinar", null=True, blank=True)
    dias_em_atraso = models.PositiveIntegerField("dias em atraso", null=True, blank=True)
    detrator_recente = models.BooleanField("detrator recente", default=False)
    total_de_checkins = models.PositiveIntegerField("check-ins registrados", default=0)
    acao = models.CharField(
        "acao sugerida", max_length=25, choices=Acao.choices, default=Acao.NENHUMA
    )
    acao_definida_em = models.DateTimeField("acao definida em", null=True, blank=True)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfis_de_risco_sob_responsabilidade",
    )
    desfecho = models.CharField(
        "desfecho", max_length=20, choices=Desfecho.choices, default=Desfecho.EM_ABERTO
    )
    observacoes = models.TextField("observacoes", blank=True)
    calculado_em = models.DateTimeField("calculado em", auto_now=True)

    class Meta:
        ordering = ["-pontuacao", "aluno__nome"]
        verbose_name = "perfil de risco"
        verbose_name_plural = "perfis de risco"
        constraints = [
            models.UniqueConstraint(fields=["aluno"], name="um_perfil_de_risco_por_aluno"),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.pontuacao} ({self.get_faixa_display()})"

    @property
    def pede_acao(self) -> bool:
        return self.faixa in {self.Faixa.ALTO, self.Faixa.CRITICO}
