"""Modelos do controle de acesso e da conciliacao com parceiros (Wellhub, TotalPass).

O ponto central e que **liberar a catraca e uma decisao registrada**: cada tentativa guarda se
entrou, por qual credencial, em que unidade e — quando negada — por qual motivo. Sem isso, uma
discussao na recepcao ("o sistema nao abriu meu acesso") nao tem como ser respondida.

A conciliacao com parceiro existe porque o dinheiro entra errado: acesso cobrado sem registro e
acesso prestado sem cobranca sao os dois lados do mesmo problema.
"""

from __future__ import annotations

from django.db import models

from core.models import Rede, Unidade


class DispositivoDeAcesso(models.Model):
    """Catraca, portaria ou totem que consulta a liberacao."""

    class Tipo(models.TextChoices):
        CATRACA = "catraca", "Catraca"
        PORTARIA = "portaria", "Portaria"
        TOTEM = "totem", "Totem"
        APLICATIVO = "aplicativo", "Aplicativo do aluno"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="dispositivos_de_acesso")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.CASCADE, related_name="dispositivos_de_acesso"
    )
    nome = models.CharField("nome", max_length=100)
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices, default=Tipo.CATRACA)
    identificador = models.CharField("identificador do equipamento", max_length=80, unique=True)
    token = models.CharField("token de integracao", max_length=64)
    ativo = models.BooleanField("ativo", default=True)
    ultima_comunicacao_em = models.DateTimeField("ultima comunicacao", null=True, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "dispositivo de acesso"
        verbose_name_plural = "dispositivos de acesso"
        ordering = ["unidade__nome", "nome"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.get_tipo_display()})"


class CredencialDeAcesso(models.Model):
    """O que o aluno apresenta na entrada: codigo do cartao, QR do app ou biometria."""

    class Tipo(models.TextChoices):
        CARTAO = "cartao", "Cartao de proximidade"
        QR = "qr", "QR do aplicativo"
        BIOMETRIA = "biometria", "Biometria"
        MANUAL = "manual", "Lancada na recepcao"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="credenciais")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="credenciais",
        verbose_name="aluno",
    )
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices, default=Tipo.CARTAO)
    codigo = models.CharField("codigo", max_length=64)
    ativa = models.BooleanField("ativa", default=True)
    emitida_em = models.DateTimeField("emitida em", auto_now_add=True)
    perdida_em = models.DateTimeField("perdida ou cancelada em", null=True, blank=True)

    class Meta:
        verbose_name = "credencial de acesso"
        verbose_name_plural = "credenciais de acesso"
        constraints = [
            models.UniqueConstraint(fields=["rede", "codigo"], name="credencial_unica_por_rede"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} de {self.aluno}"


class RegistroDeAcesso(models.Model):
    """Cada tentativa de entrar, liberada ou nao."""

    class Origem(models.TextChoices):
        CATRACA = "catraca", "Catraca"
        PORTARIA = "portaria", "Portaria"
        TOTEM = "totem", "Totem"
        APLICATIVO = "aplicativo", "Aplicativo do aluno"
        MANUAL = "manual", "Lancada na recepcao"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="acessos")
    unidade = models.ForeignKey(Unidade, on_delete=models.CASCADE, related_name="acessos")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acessos",
        verbose_name="aluno",
    )
    credencial = models.ForeignKey(
        CredencialDeAcesso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acessos",
    )
    dispositivo = models.ForeignKey(
        DispositivoDeAcesso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acessos",
    )
    liberado = models.BooleanField("liberado", default=False)
    motivo = models.CharField("motivo da negativa", max_length=200, blank=True)
    origem = models.CharField(
        "origem", max_length=12, choices=Origem.choices, default=Origem.CATRACA
    )
    codigo_apresentado = models.CharField("codigo apresentado", max_length=64, blank=True)
    itinerante = models.BooleanField("entrou em unidade diferente da de origem", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "registro de acesso"
        verbose_name_plural = "registros de acesso"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["rede", "criado_em"]),
            models.Index(fields=["rede", "liberado"]),
        ]

    def __str__(self) -> str:
        situacao = "liberado" if self.liberado else "negado"
        return (
            f"{self.aluno or self.codigo_apresentado} em {self.criado_em:%d/%m %H:%M} ({situacao})"
        )


class PlanoDeParceiro(models.Model):
    """Acordo com Wellhub, TotalPass e afins: como o acesso vira repasse."""

    class Parceiro(models.TextChoices):
        WELLHUB = "wellhub", "Wellhub (Gympass)"
        TOTALPASS = "totalpass", "TotalPass"
        CLASSPASS = "classpass", "ClassPass"
        OUTRO = "outro", "Outro parceiro"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="planos_de_parceiro")
    parceiro = models.CharField("parceiro", max_length=15, choices=Parceiro.choices)
    nome_no_parceiro = models.CharField("nome do plano no parceiro", max_length=120)
    valor_por_acesso = models.DecimalField(
        "valor por acesso", max_digits=10, decimal_places=2, default=0
    )
    percentual_do_parceiro = models.DecimalField(
        "percentual do parceiro (%)", max_digits=5, decimal_places=2, default=0
    )
    limite_de_acessos_por_mes = models.PositiveIntegerField(
        "limite de acessos por mes", default=0, help_text="0 = sem limite"
    )
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "plano de parceiro"
        verbose_name_plural = "planos de parceiro"
        constraints = [
            models.UniqueConstraint(
                fields=["rede", "parceiro", "nome_no_parceiro"], name="plano_de_parceiro_unico"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_parceiro_display()} — {self.nome_no_parceiro}"


class ExtratoDeParceiro(models.Model):
    """O extrato que o parceiro manda (CSV), com a conciliacao linha a linha."""

    class Situacao(models.TextChoices):
        IMPORTADO = "importado", "Importado"
        CONCILIADO = "conciliado", "Conciliado"
        COM_DIVERGENCIA = "com_divergencia", "Com divergencia"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="extratos_de_parceiro")
    plano_de_parceiro = models.ForeignKey(
        PlanoDeParceiro, on_delete=models.CASCADE, related_name="extratos"
    )
    competencia = models.DateField("competencia (primeiro dia do mes)")
    nome_do_arquivo = models.CharField("arquivo", max_length=200, blank=True)
    total_de_acessos = models.PositiveIntegerField("acessos no extrato", default=0)
    valor_total = models.DecimalField(
        "valor total do extrato", max_digits=12, decimal_places=2, default=0
    )
    situacao = models.CharField(
        "situacao", max_length=20, choices=Situacao.choices, default=Situacao.IMPORTADO
    )
    importado_em = models.DateTimeField("importado em", auto_now_add=True)
    conciliado_em = models.DateTimeField("conciliado em", null=True, blank=True)

    class Meta:
        verbose_name = "extrato de parceiro"
        verbose_name_plural = "extratos de parceiro"
        ordering = ["-competencia"]
        constraints = [
            models.UniqueConstraint(
                fields=["plano_de_parceiro", "competencia"], name="extrato_unico_por_competencia"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.plano_de_parceiro} — {self.competencia:%m/%Y}"

    @property
    def valor_esperado_pela_rede(self):
        """Quanto a rede recebe: valor do acesso menos o percentual do parceiro."""
        do_parceiro = self.valor_total * (self.plano_de_parceiro.percentual_do_parceiro or 0) / 100
        return (self.valor_total or 0) - do_parceiro


class LinhaDeExtrato(models.Model):
    """Uma linha do extrato do parceiro, conciliada ou nao com um registro de acesso."""

    extrato = models.ForeignKey(ExtratoDeParceiro, on_delete=models.CASCADE, related_name="linhas")
    data = models.DateField("data")
    codigo = models.CharField("codigo do aluno no parceiro", max_length=64)
    nome_informado = models.CharField("nome informado", max_length=150, blank=True)
    valor = models.DecimalField("valor", max_digits=10, decimal_places=2, default=0)
    conciliado = models.BooleanField("conciliado", default=False)
    divergencia = models.CharField("divergencia", max_length=200, blank=True)
    acesso = models.ForeignKey(
        RegistroDeAcesso,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linhas_de_extrato",
    )

    class Meta:
        verbose_name = "linha de extrato"
        verbose_name_plural = "linhas de extrato"
        ordering = ["data", "codigo"]

    def __str__(self) -> str:
        return f"{self.data:%d/%m} {self.codigo} R$ {self.valor}"
