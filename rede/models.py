"""Rede e franquias (PRD secao 18).

Cobre unidades, governanca da marca e da politica, repasses/royalties com memoria de
calculo, metas, comunicados, alcadas de aprovacao, onboarding e transferencias.
Tudo referenciando ``Rede``/``Unidade`` explicitamente: sao decisoes de rede, nao de
uma unidade isolada.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Rede, Unidade

ZERO = Decimal("0.00")


class PoliticaDaRede(models.Model):
    """O que a unidade NAO pode mudar (RF-RED-014) e como a marca e herdada (RF-RED-013)."""

    rede = models.OneToOneField(Rede, on_delete=models.CASCADE, related_name="politica",
                                verbose_name="rede")
    trava_planos_e_precos = models.BooleanField("travam planos e precos", default=True)
    trava_politica_de_desconto = models.BooleanField("trava a politica de desconto", default=True)
    teto_de_desconto = models.DecimalField("teto de desconto (%)", max_digits=5, decimal_places=2,
                                           default=Decimal("10.00"))
    trava_regua_de_cobranca = models.BooleanField("trava a regua de cobranca", default=True)
    trava_contratos = models.BooleanField("trava modelos de contrato", default=True)
    trava_cancelamento = models.BooleanField("trava politica de cancelamento", default=True)
    trava_templates_de_mensagem = models.BooleanField("trava templates de mensagem", default=True)
    permitir_sobrescrita_branding = models.BooleanField("permite sobrescrever a marca", default=False)
    dia_de_fechamento = models.PositiveSmallIntegerField("dia de fechamento do repasse", default=1)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "politica da rede"
        verbose_name_plural = "politicas da rede"

    def __str__(self) -> str:
        return f"Politica de {self.rede.nome}"

    @classmethod
    def da_rede(cls, rede) -> PoliticaDaRede:
        politica, _ = cls.objects.get_or_create(rede=rede)
        return politica

    def motivo_do_trava(self, campo: str) -> str:
        return "Definido pela rede" if getattr(self, campo, False) else ""


class RegraDeRepasse(models.Model):
    """Como o repasse/royalty e calculado (RF-RED-012)."""

    class Tipo(models.TextChoices):
        PERCENTUAL = "percentual", "Percentual sobre a base"
        PERCENTUAL_MAIS_FIXO = "percentual_mais_fixo", "Percentual + valor fixo"
        FIXO = "fixo", "Valor fixo por periodo"

    class Base(models.TextChoices):
        BRUTO = "bruto", "Faturamento bruto"
        LIQUIDO = "liquido", "Faturamento liquido (com exclusoes)"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="regras_de_repasse",
                             verbose_name="rede")
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="regras_de_repasse", verbose_name="unidade",
                                help_text="Em branco = regra padrao da rede.")
    tipo = models.CharField("tipo", max_length=25, choices=Tipo.choices, default=Tipo.PERCENTUAL)
    percentual = models.DecimalField("percentual (%)", max_digits=6, decimal_places=3,
                                     default=Decimal("0.000"))
    valor_fixo = models.DecimalField("valor fixo (R$)", max_digits=12, decimal_places=2, default=ZERO)
    base = models.CharField("base de calculo", max_length=10, choices=Base.choices,
                            default=Base.BRUTO)
    excluir_taxas_de_gateway = models.BooleanField("excluir taxas de gateway", default=True)
    excluir_estornos = models.BooleanField("excluir estornos e devolucoes", default=True)
    excluir_impostos = models.BooleanField("excluir impostos sobre a receita", default=False)
    excluir_planos_de_parceiros = models.BooleanField("excluir planos de parceiros (Wellhub etc.)",
                                                      default=False)
    percentual_de_impostos = models.DecimalField("impostos (% sobre a receita)", max_digits=5,
                                                 decimal_places=2, default=ZERO)
    percentual_de_taxas_de_gateway = models.DecimalField(
        "taxas de gateway (% sobre a receita)", max_digits=5, decimal_places=2, default=ZERO,
    )
    fundo_de_marketing = models.DecimalField("fundo de marketing (%)", max_digits=5, decimal_places=2,
                                             default=ZERO)
    piso_minimo = models.DecimalField("piso minimo (R$)", max_digits=12, decimal_places=2,
                                      default=ZERO)
    dia_de_vencimento = models.PositiveSmallIntegerField("dia de vencimento", default=10)
    inicio_da_vigencia = models.DateField("inicio da vigencia", null=True, blank=True)
    fim_da_vigencia = models.DateField("fim da vigencia", null=True, blank=True)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "regra de repasse"
        verbose_name_plural = "regras de repasse"
        ordering = ["unidade__nome", "-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["rede", "unidade"], name="uma_regra_por_unidade"),
        ]

    def __str__(self) -> str:
        alvo = self.unidade.nome if self.unidade else "padrao da rede"
        return f"{self.get_tipo_display()} ({alvo})"

    def vale_em(self, data) -> bool:
        if not self.ativo:
            return False
        if self.inicio_da_vigencia and data < self.inicio_da_vigencia:
            return False
        if self.fim_da_vigencia and data > self.fim_da_vigencia:
            return False
        return True

    @property
    def aliquota_total(self) -> Decimal:
        return (self.percentual or ZERO) + (self.fundo_de_marketing or ZERO)


class Repasse(models.Model):
    """Repasse/royalty de um periodo, com memoria de calculo auditavel (RF-RED-012)."""

    class Situacao(models.TextChoices):
        PREVISTO = "previsto", "Previsto"
        EMITIDO = "emitido", "Emitido"
        PAGO = "pago", "Pago"
        ATRASADO = "atrasado", "Atrasado"
        CANCELADO = "cancelado", "Cancelado"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="repasses",
                             verbose_name="rede")
    unidade = models.ForeignKey(Unidade, on_delete=models.PROTECT, related_name="repasses",
                               verbose_name="unidade")
    inicio = models.DateField("inicio do periodo")
    fim = models.DateField("fim do periodo")
    situacao = models.CharField("situacao", max_length=15, choices=Situacao.choices,
                               default=Situacao.PREVISTO)
    base = models.CharField("base", max_length=10, choices=RegraDeRepasse.Base.choices)
    receita_bruta = models.DecimalField("receita bruta", max_digits=14, decimal_places=2, default=ZERO)
    exclusoes = models.DecimalField("exclusoes", max_digits=14, decimal_places=2, default=ZERO)
    receita_liquida = models.DecimalField("receita liquida", max_digits=14, decimal_places=2,
                                          default=ZERO)
    base_de_calculo = models.DecimalField("base de calculo", max_digits=14, decimal_places=2,
                                         default=ZERO)
    percentual = models.DecimalField("percentual aplicado (%)", max_digits=6, decimal_places=3,
                                     default=ZERO)
    fundo_de_marketing = models.DecimalField("fundo de marketing (%)", max_digits=5, decimal_places=2,
                                             default=ZERO)
    valor_do_royalty = models.DecimalField("royalty", max_digits=14, decimal_places=2, default=ZERO)
    valor_do_fundo = models.DecimalField("fundo de marketing", max_digits=14, decimal_places=2,
                                         default=ZERO)
    valor_fixo = models.DecimalField("valor fixo", max_digits=14, decimal_places=2, default=ZERO)
    valor_devido = models.DecimalField("valor devido", max_digits=14, decimal_places=2, default=ZERO)
    piso_aplicado = models.BooleanField("piso minimo aplicado", default=False)
    valor_pago = models.DecimalField("valor pago", max_digits=14, decimal_places=2, default=ZERO)
    vencimento = models.DateField("vencimento")
    emitido_em = models.DateTimeField("emitido em", null=True, blank=True)
    pago_em = models.DateTimeField("pago em", null=True, blank=True)
    memoria = models.JSONField("memoria de calculo", default=dict, blank=True)
    hash_do_calculo = models.CharField("hash do calculo", max_length=64, blank=True)
    observacoes = models.TextField("observacoes", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "repasse"
        verbose_name_plural = "repasses"
        ordering = ["-inicio", "unidade__nome"]
        constraints = [
            models.UniqueConstraint(fields=["unidade", "inicio", "fim"], name="um_repasse_por_periodo"),
        ]

    def __str__(self) -> str:
        return f"{self.unidade.nome} {self.inicio:%m/%Y}"

    @property
    def atrasado(self) -> bool:
        if self.situacao in {self.Situacao.PAGO, self.Situacao.CANCELADO}:
            return False
        return self.vencimento < timezone.localdate()

    @property
    def saldo(self) -> Decimal:
        return (self.valor_devido or ZERO) - (self.valor_pago or ZERO)

    def recalcular_hash(self) -> str:
        """Assinatura reproduzivel do calculo (mesmo periodo -> mesmo numero)."""
        dados = {
            "unidade": self.unidade_id,
            "periodo": [str(self.inicio), str(self.fim)],
            "base": self.base,
            "receita_bruta": str(self.receita_bruta),
            "exclusoes": str(self.exclusoes),
            "base_de_calculo": str(self.base_de_calculo),
            "percentual": str(self.percentual),
            "fundo": str(self.fundo_de_marketing),
            "valor_fixo": str(self.valor_fixo),
            "valor_devido": str(self.valor_devido),
            "itens": [
                [item.descricao, str(item.base), str(item.percentual), str(item.valor)]
                for item in self.itens.all().order_by("ordem")
            ],
        }
        bruto = json.dumps(dados, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


class ItemDeRepasse(models.Model):
    """Linha da memoria de calculo -- e o que a unidade confere (RF-RED-012)."""

    class Tipo(models.TextChoices):
        RECEITA = "receita", "Receita do periodo"
        EXCLUSAO = "exclusao", "Exclusao da base"
        ROYALTY = "royalty", "Royalty"
        FUNDO = "fundo", "Fundo de marketing"
        FIXO = "fixo", "Valor fixo"
        PISO = "piso", "Ajuste de piso minimo"

    repasse = models.ForeignKey(Repasse, on_delete=models.CASCADE, related_name="itens",
                               verbose_name="repasse")
    ordem = models.PositiveSmallIntegerField("ordem", default=1)
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    descricao = models.CharField("descricao", max_length=200)
    base = models.DecimalField("base", max_digits=14, decimal_places=2, default=ZERO)
    percentual = models.DecimalField("percentual (%)", max_digits=6, decimal_places=3, default=ZERO)
    valor = models.DecimalField("valor", max_digits=14, decimal_places=2, default=ZERO)
    referencia = models.CharField("referencia", max_length=120, blank=True)

    class Meta:
        verbose_name = "item do repasse"
        verbose_name_plural = "itens do repasse"
        ordering = ["ordem", "pk"]

    def __str__(self) -> str:
        return self.descricao


class Meta(models.Model):
    """Meta da rede ou de uma unidade por periodo (RF-RED-008)."""

    class Indicador(models.TextChoices):
        FATURAMENTO = "faturamento", "Faturamento"
        NOVAS_MATRICULAS = "novas_matriculas", "Novas matriculas"
        RETENCAO = "retencao", "Retencao (%)"
        OCUPACAO = "ocupacao", "Ocupacao das turmas (%)"
        TICKET_MEDIO = "ticket_medio", "Ticket medio (R$)"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="metas", verbose_name="rede")
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="metas", verbose_name="unidade",
                                help_text="Em branco = meta da rede inteira.")
    inicio = models.DateField("inicio do periodo")
    fim = models.DateField("fim do periodo")
    indicador = models.CharField("indicador", max_length=20, choices=Indicador.choices)
    alvo = models.DecimalField("alvo", max_digits=14, decimal_places=2)
    realizado = models.DecimalField("realizado", max_digits=14, decimal_places=2, default=ZERO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "meta"
        verbose_name_plural = "metas"
        ordering = ["-inicio", "indicador"]
        constraints = [
            models.UniqueConstraint(fields=["rede", "unidade", "inicio", "fim", "indicador"],
                                    name="uma_meta_por_indicador_e_periodo"),
        ]

    def __str__(self) -> str:
        return f"{self.get_indicador_display()} - {self.unidade or self.rede}"

    @property
    def atingimento(self) -> Decimal:
        if not self.alvo:
            return ZERO
        return (self.realizado / self.alvo * 100).quantize(Decimal("0.01"))

    @property
    def atingida(self) -> bool:
        return self.realizado >= self.alvo


class Comunicado(models.Model):
    """Aviso da rede para unidades ou campanha para alunos (RF-RED-015)."""

    class Publico(models.TextChoices):
        UNIDADES = "unidades", "Equipe das unidades"
        ALUNOS = "alunos", "Alunos da rede"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="comunicados",
                             verbose_name="rede")
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="comunicados", verbose_name="unidade",
                                help_text="Em branco = todas as unidades.")
    titulo = models.CharField("titulo", max_length=160)
    mensagem = models.TextField("mensagem")
    publico = models.CharField("publico", max_length=10, choices=Publico.choices,
                               default=Publico.UNIDADES)
    exige_confirmacao = models.BooleanField("exige confirmacao de leitura", default=True)
    ativo = models.BooleanField("ativo", default=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="comunicados_criados",
                                   verbose_name="criado por")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "comunicado"
        verbose_name_plural = "comunicados"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo

    @property
    def leituras(self) -> int:
        return self.confirmacoes.count()


class LeituraDeComunicado(models.Model):
    """Confirmacao de leitura do comunicado (RF-RED-015)."""

    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name="confirmacoes",
                                  verbose_name="comunicado")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="comunicados_lidos", verbose_name="usuario")
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="leituras", verbose_name="unidade")
    lida_em = models.DateTimeField("lida em", auto_now_add=True)

    class Meta:
        verbose_name = "leitura de comunicado"
        verbose_name_plural = "leituras de comunicado"
        ordering = ["-lida_em"]
        constraints = [
            models.UniqueConstraint(fields=["comunicado", "usuario"], name="uma_leitura_por_usuario"),
        ]

    def __str__(self) -> str:
        return f"{self.comunicado} -> {self.usuario}"


class SolicitacaoDeAprovacao(models.Model):
    """Alcadas: operacao sensivel que a unidade pede e a rede decide (RF-RED-018)."""

    class Tipo(models.TextChoices):
        DESCONTO_ACIMA_DO_TETO = "desconto", "Desconto acima do teto"
        CANCELAMENTO_COM_MULTA = "cancelamento", "Cancelamento com multa"
        TRANSFERENCIA_DE_ALUNO = "transferencia", "Transferencia de aluno"
        ALTERACAO_DE_PRECO = "preco", "Alteracao de preco"
        EXCLUSAO_EM_LOTE = "exclusao", "Exclusao em lote"
        NOVA_UNIDADE = "nova_unidade", "Abertura de unidade"

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADA = "aprovada", "Aprovada"
        RECUSADA = "recusada", "Recusada"
        CANCELADA = "cancelada", "Cancelada"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="aprovacoes",
                             verbose_name="rede")
    unidade = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="aprovacoes", verbose_name="unidade")
    tipo = models.CharField("tipo", max_length=15, choices=Tipo.choices)
    titulo = models.CharField("titulo", max_length=160)
    descricao = models.TextField("descricao", blank=True)
    valor = models.DecimalField("valor envolvido (R$)", max_digits=14, decimal_places=2, default=ZERO)
    contexto = models.JSONField("contexto", default=dict, blank=True)
    situacao = models.CharField("situacao", max_length=12, choices=Situacao.choices,
                               default=Situacao.PENDENTE)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="aprovacoes_pedidas",
                                    verbose_name="solicitante")
    decidido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="aprovacoes_decididas",
                                     verbose_name="decidido por")
    decidido_em = models.DateTimeField("decidido em", null=True, blank=True)
    justificativa = models.TextField("justificativa", blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "solicitacao de aprovacao"
        verbose_name_plural = "solicitacoes de aprovacao"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} - {self.titulo}"

    def decidir(self, usuario, aprovar: bool, justificativa: str = "") -> None:
        self.situacao = self.Situacao.APROVADA if aprovar else self.Situacao.RECUSADA
        self.decidido_por = usuario
        self.decidido_em = timezone.now()
        self.justificativa = justificativa
        self.save(update_fields=["situacao", "decidido_por", "decidido_em", "justificativa"])


class TemplateDeUnidade(models.Model):
    """Modelo de configuracao aplicado numa unidade nova (RF-RED-016)."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="templates_de_unidade",
                             verbose_name="rede")
    nome = models.CharField("nome", max_length=120)
    descricao = models.CharField("descricao", max_length=200, blank=True)
    configuracoes = models.JSONField("configuracoes", default=dict, blank=True,
                                     help_text="Planos, grades, mensagens, marca e usuarios padrao.")
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "template de unidade"
        verbose_name_plural = "templates de unidade"
        ordering = ["nome"]

    def __str__(self) -> str:
        return self.nome


class ItemDeChecklist(models.Model):
    """Passo do checklist de implantacao (RF-RED-016)."""

    template = models.ForeignKey(TemplateDeUnidade, on_delete=models.CASCADE, related_name="itens",
                                verbose_name="template")
    titulo = models.CharField("titulo", max_length=160)
    ordem = models.PositiveSmallIntegerField("ordem", default=1)
    obrigatorio = models.BooleanField("obrigatorio", default=True)

    class Meta:
        verbose_name = "item do checklist"
        verbose_name_plural = "itens do checklist"
        ordering = ["ordem", "pk"]

    def __str__(self) -> str:
        return self.titulo


class ImplantacaoDeUnidade(models.Model):
    """Execucao do template numa unidade, com o checklist (RF-RED-016)."""

    unidade = models.OneToOneField(Unidade, on_delete=models.CASCADE, related_name="implantacao",
                                   verbose_name="unidade")
    template = models.ForeignKey(TemplateDeUnidade, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="implantacoes", verbose_name="template")
    aplicado_em = models.DateTimeField("aplicado em", auto_now_add=True)
    concluida_em = models.DateTimeField("concluida em", null=True, blank=True)
    itens_concluidos = models.JSONField("itens concluidos", default=list, blank=True)
    resultado = models.JSONField("resultado da aplicacao", default=dict, blank=True)

    class Meta:
        verbose_name = "implantacao de unidade"
        verbose_name_plural = "implantacoes de unidade"

    def __str__(self) -> str:
        return f"Implantacao de {self.unidade.nome}"

    @property
    def progresso(self) -> int:
        total = self.template.itens.count() if self.template else 0
        if not total:
            return 100
        return int(len(self.itens_concluidos or []) / total * 100)


class TransferenciaDeAluno(models.Model):
    """Historico de transferencia de aluno entre unidades (RF-RED-004/024)."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="transferencias",
                             verbose_name="rede")
    aluno = models.ForeignKey("usuarios.Usuario", on_delete=models.CASCADE,
                              related_name="transferencias", verbose_name="aluno")
    origem = models.ForeignKey(Unidade, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="transferencias_de_saida", verbose_name="unidade de origem")
    destino = models.ForeignKey(Unidade, on_delete=models.PROTECT,
                                related_name="transferencias_de_entrada", verbose_name="unidade de destino")
    motivo = models.CharField("motivo", max_length=200, blank=True)
    autorizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="transferencias_autorizadas",
                                       verbose_name="autorizado por")
    lote = models.CharField("lote", max_length=40, blank=True, help_text="Agrupa transferencias em lote.")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "transferencia de aluno"
        verbose_name_plural = "transferencias de aluno"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.aluno} -> {self.destino}"


class DistribuicaoDeCatalogo(models.Model):
    """Distribuicao em lote de aulas/treinos da rede para unidades (RF-RED-006)."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="distribuicoes",
                             verbose_name="rede")
    referencia = models.CharField("aula/treino de origem", max_length=120)
    unidades = models.JSONField("unidades", default=list, blank=True)
    resultado = models.JSONField("resultado", default=dict, blank=True)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="distribuicoes_criadas",
                                   verbose_name="criado por")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "distribuicao de catalogo"
        verbose_name_plural = "distribuicoes de catalogo"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.referencia} -> {len(self.unidades or [])} unidade(s)"
