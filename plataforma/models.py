"""Entidades da plataforma: pacotes, assinaturas, faturas e cobranca (PRD secao 10.1)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from api.auditoria import registrar
from core.models import Rede
from core.papeis import StatusRede


class ModuloPacote(models.TextChoices):
    """Modulos que cada pacote pode ligar (feature flags, RF-PLT-011)."""

    WHATSAPP = "whatsapp", "WhatsApp"
    RELATORIOS_AVANCADOS = "relatorios_avancados", "Relatorios avancados"
    API = "api", "API e integracoes"
    DOMINIO_PROPRIO = "dominio_proprio", "Dominio proprio"
    MULTI_UNIDADE = "multi_unidade", "Rede com varias unidades"
    IMPRESSAO_PDF = "impressao_pdf", "Impressao e PDF"
    SUPORTE_PRIORITARIO = "suporte_prioritario", "Suporte prioritario"


class Ciclo(models.TextChoices):
    MENSAL = "mensal", "Mensal"
    ANUAL = "anual", "Anual"


class StatusFatura(models.TextChoices):
    ABERTA = "aberta", "Aberta"
    PAGA = "paga", "Paga"
    VENCIDA = "vencida", "Vencida"
    CANCELADA = "cancelada", "Cancelada"
    ESTORNADA = "estornada", "Estornada"


class FormaPagamento(models.TextChoices):
    PIX = "pix", "Pix"
    BOLETO = "boleto", "Boleto"
    CARTAO = "cartao", "Cartao"


class MarcoRegua(models.TextChoices):
    """Marcos da regua de cobranca (RF-PLT-023) e avisos de limite/trial."""

    TRIAL_7 = "T-7", "Trial: faltam 7 dias"
    TRIAL_3 = "T-3", "Trial: faltam 3 dias"
    TRIAL_1 = "T-1", "Trial: ultimo dia"
    D3 = "D-3", "Vencimento em 3 dias"
    D0 = "D0", "Vence hoje"
    D1 = "D+1", "1 dia de atraso"
    D5 = "D+5", "5 dias: aviso de bloqueio"
    D10 = "D+10", "10 dias: bloqueio de escrita"
    D30 = "D+30", "30 dias: suspensao"
    LIMITE_80 = "L80", "Limite do pacote em 80%"
    LIMITE_95 = "L95", "Limite do pacote em 95%"


class CanalCobranca(models.TextChoices):
    EMAIL = "email", "E-mail"
    WHATSAPP = "whatsapp", "WhatsApp"
    PAINEL = "painel", "Painel"


class ResultadoDisparo(models.TextChoices):
    ENVIADO = "enviado", "Enviado"
    FALHA = "falha", "Falha"
    IGNORADO = "ignorado", "Ignorado"


class Pacote(models.Model):
    """O que a SafeStack vende (Prata/Bronze/Ouro)."""

    nome = models.CharField("nome", max_length=60)
    codigo = models.SlugField("codigo", max_length=40, unique=True)
    descricao = models.CharField("descricao", max_length=255, blank=True)
    limite_alunos = models.PositiveIntegerField("limite de alunos", null=True, blank=True)
    limite_professores = models.PositiveIntegerField("limite de professores", null=True, blank=True)
    limite_unidades = models.PositiveIntegerField("limite de unidades", null=True, blank=True)
    preco_mensal = models.DecimalField("preco mensal", max_digits=10, decimal_places=2, default=Decimal("0"))
    preco_anual = models.DecimalField("preco anual", max_digits=10, decimal_places=2, default=Decimal("0"))
    modulos = models.JSONField("modulos habilitados", default=list, blank=True)
    ordem_exibicao = models.PositiveSmallIntegerField("ordem de exibicao", default=0)
    visivel_no_site = models.BooleanField("visivel no site", default=True)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "pacote"
        verbose_name_plural = "pacotes"
        ordering = ["ordem_exibicao", "preco_mensal"]

    def __str__(self) -> str:
        return self.nome

    def limite_de(self, recurso: str) -> int | None:
        """Limite do pacote para ``alunos``, ``professores`` ou ``unidades`` (None = ilimitado)."""
        return {
            "alunos": self.limite_alunos,
            "professores": self.limite_professores,
            "unidades": self.limite_unidades,
        }.get(recurso)

    def tem_modulo(self, modulo: str) -> bool:
        return modulo in (self.modulos or [])

    def preco_do_ciclo(self, ciclo: str) -> Decimal:
        mensal = Decimal(str(self.preco_mensal or 0))
        if str(ciclo) == Ciclo.ANUAL:
            return Decimal(str(self.preco_anual)) if self.preco_anual else mensal * 12
        return mensal


class Assinatura(models.Model):
    """Contrato do tenant (rede) com um pacote."""

    rede = models.OneToOneField(Rede, on_delete=models.CASCADE, related_name="assinatura",
                                verbose_name="rede")
    pacote = models.ForeignKey(Pacote, on_delete=models.PROTECT, related_name="assinaturas",
                               verbose_name="pacote")
    ciclo = models.CharField("ciclo", max_length=10, choices=Ciclo.choices, default=Ciclo.MENSAL)
    inicio = models.DateField("inicio", default=timezone.localdate)
    renovacao_em = models.DateField("proxima renovacao")
    trial_termina_em = models.DateField("teste termina em", null=True, blank=True)
    cancelada_em = models.DateField("cancelada em", null=True, blank=True)
    limite_alunos_custom = models.PositiveIntegerField("limite de alunos (excecao)", null=True, blank=True)
    limite_professores_custom = models.PositiveIntegerField("limite de professores (excecao)", null=True, blank=True)
    limite_unidades_custom = models.PositiveIntegerField("limite de unidades (excecao)", null=True, blank=True)
    motivo_excecao = models.TextField("motivo da excecao", blank=True)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="excecoes_autorizadas",
                                       verbose_name="autorizado por")
    pacote_agendado = models.ForeignKey(Pacote, null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name="agendadas", verbose_name="pacote agendado")
    desconto_percentual = models.DecimalField("desconto (%)", max_digits=5, decimal_places=2,
                                              default=Decimal("0"))
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "assinatura"
        verbose_name_plural = "assinaturas"
        ordering = ["rede__nome"]

    def __str__(self) -> str:
        return f"{self.rede} - {self.pacote}"

    @property
    def em_trial(self) -> bool:
        return bool(self.trial_termina_em and self.trial_termina_em >= timezone.localdate())

    @property
    def trial_acabou(self) -> bool:
        return bool(self.trial_termina_em and self.trial_termina_em < timezone.localdate())

    @property
    def cancelada(self) -> bool:
        return self.cancelada_em is not None

    def limite_efetivo(self, recurso: str) -> int | None:
        """RF-PLT-013: vale o mais restritivo entre pacote e excecao comercial."""
        do_pacote = self.pacote.limite_de(recurso)
        custom = {
            "alunos": self.limite_alunos_custom,
            "professores": self.limite_professores_custom,
            "unidades": self.limite_unidades_custom,
        }.get(recurso)
        if custom is None:
            return do_pacote
        if do_pacote is None:
            return custom
        return min(do_pacote, custom)

    def limites_efetivos(self) -> dict[str, int | None]:
        return {r: self.limite_efetivo(r) for r in ("alunos", "professores", "unidades")}

    def tem_modulo(self, modulo: str) -> bool:
        return self.pacote.tem_modulo(modulo)

    def valor_do_ciclo(self) -> Decimal:
        bruto = Decimal(str(self.pacote.preco_do_ciclo(self.ciclo)))
        desconto = Decimal(str(self.desconto_percentual or 0))
        if desconto:
            bruto = bruto * (Decimal("1") - desconto / Decimal("100"))
        return bruto.quantize(Decimal("0.01"))

    def trocar_pacote(self, pacote: Pacote, ciclo: str | None = None, hoje=None):
        """Upgrade cobra a diferenca proporcional; downgrade vale no proximo ciclo.

        Devolve a ``Fatura`` proporcional (upgrade) ou ``None``.
        """
        hoje = hoje or timezone.localdate()
        ciclo = ciclo or self.ciclo
        mesmos_limites = pacote.limite_de("alunos") == self.pacote.limite_de("alunos")
        subiu = (pacote.limite_de("alunos") or 10**9) >= (self.pacote.limite_de("alunos") or 10**9)
        fatura = None
        if subiu and not mesmos_limites and not self.em_trial:
            dias_restantes = max((self.renovacao_em - hoje).days, 0)
            diferenca = pacote.preco_do_ciclo(ciclo) - self.pacote.preco_do_ciclo(self.ciclo)
            if diferenca > 0 and dias_restantes > 0:
                proporciona = (diferenca / 30 * dias_restantes).quantize(Decimal("0.01"))
                fatura = Fatura.objects.create(
                    rede=self.rede,
                    assinatura=self,
                    periodo_inicio=hoje,
                    periodo_fim=self.renovacao_em,
                    vencimento=hoje + timedelta(days=3),
                    valor=proporciona,
                    valor_final=proporciona,
                    observacao=f"Upgrade proporcional para {pacote.nome} ({dias_restantes} dias restantes)",
                )
        self.pacote = pacote
        self.ciclo = ciclo
        if self.renovacao_em < hoje:
            self.renovacao_em = Fatura.proximo_vencimento(hoje, ciclo)
        self.save(update_fields=["pacote", "ciclo", "renovacao_em", "atualizado_em"])
        if self.rede.status == StatusRede.CANCELADO:
            self.rede.status = StatusRede.ATIVO
            self.rede.save(update_fields=["status"])
        return fatura

    def cancelar(self, quando=None):
        self.cancelada_em = quando or timezone.localdate()
        self.save(update_fields=["cancelada_em", "atualizado_em"])
        self.rede.status = StatusRede.CANCELADO
        self.rede.save(update_fields=["status"])

    def agendar_troca(self, pacote: Pacote):
        """Downgrade vale na proxima renovacao (nada e apagado) -- PRD 11.3."""
        self.pacote_agendado = pacote
        self.save(update_fields=["pacote_agendado", "atualizado_em"])
        return self

    def aplicar_troca_agendada(self):
        if self.pacote_agendado_id is None:
            return False
        self.pacote = self.pacote_agendado
        self.pacote_agendado = None
        self.save(update_fields=["pacote", "pacote_agendado", "atualizado_em"])
        registrar("alterar", "assinatura", entidade_id=self.pk,
                  descricao=f"Pacote {self.pacote.nome} aplicado na renovacao")
        return True


class Fatura(models.Model):
    """Cobranca da plataforma sobre o tenant."""

    DIAS_POR_CICLO = {Ciclo.MENSAL: 30, Ciclo.ANUAL: 365}

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="faturas",
                             verbose_name="rede")
    assinatura = models.ForeignKey(Assinatura, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="faturas", verbose_name="assinatura")
    numero = models.CharField("numero", max_length=24, unique=True, blank=True)
    periodo_inicio = models.DateField("periodo de")
    periodo_fim = models.DateField("periodo ate")
    vencimento = models.DateField("vencimento")
    valor = models.DecimalField("valor", max_digits=10, decimal_places=2)
    desconto = models.DecimalField("desconto", max_digits=10, decimal_places=2, default=Decimal("0"))
    valor_final = models.DecimalField("valor final", max_digits=10, decimal_places=2)
    status = models.CharField("status", max_length=12, choices=StatusFatura.choices,
                              default=StatusFatura.ABERTA)
    pago_em = models.DateField("pago em", null=True, blank=True)
    forma_pagamento = models.CharField("forma", max_length=10, choices=FormaPagamento.choices,
                                       blank=True)
    gateway = models.CharField("gateway", max_length=20, blank=True)
    gateway_id = models.CharField("id no gateway", max_length=80, blank=True)
    pix_qr_code = models.TextField("QR code (Pix)", blank=True)
    pix_copia_cola = models.TextField("Pix copia e cola", blank=True)
    link_pagamento = models.CharField("link de pagamento", max_length=255, blank=True)
    observacao = models.TextField("observacao", blank=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "fatura"
        verbose_name_plural = "faturas"
        ordering = ["-vencimento", "-id"]

    def __str__(self) -> str:
        return f"{self.numero} - {self.rede} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.valor_final:
            self.valor_final = Decimal(str(self.valor or 0)) - Decimal(str(self.desconto or 0))
        super().save(*args, **kwargs)
        if not self.numero:
            self.numero = f"FAT-{self.criada_em.year}-{self.pk:05d}"
            super().save(update_fields=["numero"])

    @classmethod
    def proximo_vencimento(cls, base, ciclo: str):
        return base + timedelta(days=cls.DIAS_POR_CICLO.get(str(ciclo), 30))

    @property
    def em_aberto(self) -> bool:
        return self.status in {StatusFatura.ABERTA, StatusFatura.VENCIDA}

    @property
    def dias_de_atraso(self) -> int:
        if not self.em_aberto:
            return 0
        return max((timezone.localdate() - self.vencimento).days, 0)

    def marcar_paga(self, valor_pago=None, forma=FormaPagamento.PIX, quando=None, gateway_id=""):
        """Baixa da fatura. Idempotente: fatura ja paga devolve False (RF-PLT-022)."""
        if self.status == StatusFatura.PAGA:
            return False
        self.status = StatusFatura.PAGA
        self.pago_em = quando or timezone.localdate()
        self.forma_pagamento = forma or FormaPagamento.PIX
        if gateway_id:
            self.gateway_id = gateway_id
        if valor_pago is not None:
            self.observacao = (self.observacao + f"\nPago: {valor_pago}").strip()
        self.save()
        return True

    def cancelar(self, motivo=""):
        self.status = StatusFatura.CANCELADA
        if motivo:
            self.observacao = f"{self.observacao}\nCancelada: {motivo}".strip()
        self.save()


class EventoCobranca(models.Model):
    """Registro de cada disparo da regua (RF-PLT-023): nao repete nem perde."""

    fatura = models.ForeignKey(Fatura, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="eventos", verbose_name="fatura")
    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="eventos_cobranca",
                             verbose_name="rede")
    marco = models.CharField("marco", max_length=6, choices=MarcoRegua.choices)
    canal = models.CharField("canal", max_length=10, choices=CanalCobranca.choices,
                             default=CanalCobranca.EMAIL)
    status = models.CharField("status", max_length=10, choices=ResultadoDisparo.choices,
                              default=ResultadoDisparo.ENVIADO)
    mensagem = models.TextField("mensagem", blank=True)
    erro = models.TextField("erro", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "evento de cobranca"
        verbose_name_plural = "eventos de cobranca"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["fatura", "marco", "canal"], name="unico_evento_por_marco"),
        ]

    def __str__(self) -> str:
        return f"{self.rede} {self.marco} ({self.get_status_display()})"


class EventoGateway(models.Model):
    """Evento recebido do gateway. (idempotencia por ``evento_id``, RF-PLT-022)."""

    gateway = models.CharField("gateway", max_length=20)
    evento_id = models.CharField("id do evento", max_length=120, unique=True)
    tipo = models.CharField("tipo", max_length=60, blank=True)
    payload = models.JSONField("payload", default=dict, blank=True)
    resultado = models.CharField("resultado", max_length=120, blank=True)
    erro = models.TextField("erro", blank=True)
    processado_em = models.DateTimeField("processado em", null=True, blank=True)
    recebido_em = models.DateTimeField("recebido em", auto_now_add=True)

    class Meta:
        verbose_name = "evento de gateway"
        verbose_name_plural = "eventos de gateway"
        ordering = ["-recebido_em"]

    def __str__(self) -> str:
        return f"{self.gateway}:{self.evento_id}"


class ConfiguracaoPlataforma(models.Model):
    """Configuracao unica da plataforma (gateway, regua, dados do emitente)."""

    nome_emitente = models.CharField("nome do emitente", max_length=120, default="SafeStack")
    cnpj_emitente = models.CharField("CNPJ do emitente", max_length=20, blank=True)
    email_financeiro = models.EmailField("e-mail financeiro", blank=True)
    asaas_api_key = models.CharField("chave da API Asaas", max_length=255, blank=True)
    asaas_ambiente = models.CharField("ambiente Asaas", max_length=10,
                                      choices=[("sandbox", "Sandbox"), ("producao", "Producao")],
                                      default="sandbox")
    asaas_base_url = models.CharField("URL base da API", max_length=120, blank=True)
    token_webhook = models.CharField("token do webhook", max_length=120, blank=True)
    trial_dias = models.PositiveSmallIntegerField("dias de teste", default=14)
    dias_bloqueio = models.PositiveSmallIntegerField("dias para bloqueio de escrita", default=10)
    dias_suspensao = models.PositiveSmallIntegerField("dias para suspensao", default=30)
    multa_percentual = models.DecimalField("multa (%)", max_digits=5, decimal_places=2,
                                           default=Decimal("2"))
    juros_dia_percentual = models.DecimalField("juros ao dia (%)", max_digits=6,
                                               decimal_places=3, default=Decimal("0.033"))
    regua_ativa = models.BooleanField("regua de cobranca ativa", default=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "configuracao da plataforma"
        verbose_name_plural = "configuracao da plataforma"

    def __str__(self) -> str:
        return f"Configuracao da plataforma ({self.asaas_ambiente})"

    def save(self, *args, **kwargs):
        if not self.pk and ConfiguracaoPlataforma.objects.exists():
            from django.core.exceptions import ValidationError

            raise ValidationError("A configuracao da plataforma e unica.")
        return super().save(*args, **kwargs)

    @classmethod
    def obter(cls) -> ConfiguracaoPlataforma:
        return cls.objects.first() or cls.objects.create()

    @property
    def gateway_em_modo_simulado(self) -> bool:
        return not self.asaas_api_key


class Impersonacao(models.Model):
    """Acesso de suporte auditado ao tenant (RF-PLT-007)."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="impersonacoes",
                             verbose_name="rede")
    usuario_plataforma = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                           related_name="impersonacoes_feitas",
                                           verbose_name="usuario da plataforma")
    usuario_alvo = models.CharField("usuario alvo", max_length=150, blank=True)
    motivo = models.TextField("motivo")
    inicio = models.DateTimeField("inicio", default=timezone.now)
    fim = models.DateTimeField("fim", null=True, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("user agent", max_length=200, blank=True)
    acoes = models.PositiveIntegerField("acoes registradas", default=0)

    class Meta:
        verbose_name = "impersonacao"
        verbose_name_plural = "impersonacoes"
        ordering = ["-inicio"]

    def __str__(self) -> str:
        return f"{self.usuario_plataforma} como {self.rede} ({self.inicio:%d/%m/%Y %H:%M})"

    @property
    def ativa(self) -> bool:
        return self.fim is None

    @property
    def duracao(self):
        return (self.fim or timezone.now()) - self.inicio

    def encerrar(self, quando=None):
        self.fim = quando or timezone.now()
        self.save(update_fields=["fim"])
        return self
