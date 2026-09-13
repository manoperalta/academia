"""Modelos de treino: prescricao, execucao e avaliacao fisica.

Tres ideias guiam este app:

* **Prescricao e historico, nao planilha solta** — o treino guarda os exercicios na ordem, com series,
  repeticoes e carga sugerida, e cada execucao registra o que o aluno realmente fez.
* **Avaliacao fisica e evolucao comparavel** — medidas e composicao guardadas por data, para a tela
  mostrar a diferenca entre a primeira e a ultima avaliacao, e nao um numero parado.
* **Ficha de saude manda** — exercicio que exige cuidado (restricao) aparece sinalizado quando o
  aluno tem aquela restricao registrada na ficha de saude.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from core.models import Rede, Unidade

MEDIDAS = (
    ("cintura", "Cintura"),
    ("quadril", "Quadril"),
    ("peito", "Peito"),
    ("braco", "Braco"),
    ("coxa", "Coxa"),
    ("panturrilha", "Panturrilha"),
    ("ombro", "Ombro"),
    ("abdomen", "Abdomen"),
)


class Treino(models.Model):
    """Prescricao de treino de um aluno, feita por um professor."""

    class Objetivo(models.TextChoices):
        HIPERTROFIA = "hipertrofia", "Hipertrofia"
        EMAGRECIMENTO = "emagrecimento", "Emagrecimento"
        CONDICIONAMENTO = "condicionamento", "Condicionamento"
        FORCA = "forca", "Forca"
        REABILITACAO = "reabilitacao", "Reabilitacao"
        MOBILIDADE = "mobilidade", "Mobilidade"

    class Situacao(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ATIVO = "ativo", "Ativo"
        CONCLUIDO = "concluido", "Concluido"
        CANCELADO = "cancelado", "Cancelado"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="treinos")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="treinos"
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE, related_name="treinos", verbose_name="aluno"
    )
    professor = models.ForeignKey(
        "professores.Professor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="treinos",
        verbose_name="professor",
    )
    nome = models.CharField("nome", max_length=120)
    objetivo = models.CharField(
        "objetivo", max_length=20, choices=Objetivo.choices, default=Objetivo.CONDICIONAMENTO
    )
    observacoes = models.TextField("observacoes", blank=True)
    inicio = models.DateField("inicio", null=True, blank=True)
    fim = models.DateField("fim", null=True, blank=True)
    situacao = models.CharField(
        "situacao", max_length=10, choices=Situacao.choices, default=Situacao.RASCUNHO
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "treino"
        verbose_name_plural = "treinos"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["rede", "situacao"])]

    def __str__(self) -> str:
        return f"{self.nome} — {self.aluno}"

    @property
    def total_de_exercicios(self) -> int:
        return self.exercicios.count()

    @property
    def esta_ativo(self) -> bool:
        return self.situacao == self.Situacao.ATIVO


class ExercicioDoTreino(models.Model):
    """Um exercicio da prescricao, podendo apontar para a videoaula que ensina a execucao."""

    treino = models.ForeignKey(Treino, on_delete=models.CASCADE, related_name="exercicios")
    aula = models.ForeignKey(
        "aulas.Aulas",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercicios_prescritos",
        verbose_name="videoaula",
    )
    nome = models.CharField("exercicio", max_length=150)
    series = models.PositiveSmallIntegerField("series", default=3)
    repeticoes = models.CharField("repeticoes", max_length=30, default="12")
    carga_sugerida = models.DecimalField(
        "carga sugerida (kg)", max_digits=6, decimal_places=2, default=0
    )
    descanso_segundos = models.PositiveSmallIntegerField("descanso (s)", default=60)
    ordem = models.PositiveSmallIntegerField("ordem", default=1)
    observacoes = models.CharField("observacoes", max_length=200, blank=True)

    class Meta:
        verbose_name = "exercicio do treino"
        verbose_name_plural = "exercicios do treino"
        ordering = ["ordem", "pk"]

    def __str__(self) -> str:
        return f"{self.ordem}. {self.nome} ({self.series}x{self.repeticoes})"

    @property
    def tem_restricao_conflitante(self) -> bool:
        """Sinaliza quando a videoaula exige cuidado que o aluno tem registrado na ficha."""
        if self.aula is None or not self.aula.restricao or self.aula.restricao == "nenhuma":
            return False
        from usuarios.models import FichaSaude

        ficha = FichaSaude.todos.filter(usuario=self.treino.aluno).first()
        if ficha is None:
            return False
        restricoes = (ficha.restricoes or "").lower()
        return self.aula.restricao.lower() in restricoes


class ExecucaoDoExercicio(models.Model):
    """O que o aluno fez de fato: carga e repeticoes por data."""

    exercicio = models.ForeignKey(
        ExercicioDoTreino, on_delete=models.CASCADE, related_name="execucoes"
    )
    data = models.DateField("data")
    carga = models.DecimalField("carga (kg)", max_digits=6, decimal_places=2, default=0)
    repeticoes = models.CharField("repeticoes feitas", max_length=30, blank=True)
    esforco_percebido = models.PositiveSmallIntegerField("esforco percebido (1-10)", default=0)
    observacoes = models.CharField("observacoes", max_length=200, blank=True)
    registrado_em = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "execucao do exercicio"
        verbose_name_plural = "execucoes do exercicio"
        ordering = ["-data"]

    def __str__(self) -> str:
        return f"{self.exercicio.nome} em {self.data:%d/%m/%Y}: {self.carga} kg"


class AvaliacaoFisica(models.Model):
    """Medidas e composicao corporal, por data — a base da tela de evolucao."""

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="avaliacoes_fisicas")
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_fisicas",
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="avaliacoes_fisicas",
        verbose_name="aluno",
    )
    avaliador = models.ForeignKey(
        "professores.Professor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_realizadas",
        verbose_name="avaliador",
    )
    data = models.DateField("data")
    peso = models.DecimalField("peso (kg)", max_digits=5, decimal_places=2, default=0)
    altura = models.DecimalField("altura (m)", max_digits=4, decimal_places=2, default=0)
    percentual_de_gordura = models.DecimalField(
        "percentual de gordura (%)", max_digits=4, decimal_places=1, default=0
    )
    massa_muscular = models.DecimalField(
        "massa muscular (kg)", max_digits=5, decimal_places=2, default=0
    )
    medidas = models.JSONField("medidas (cm)", default=dict, blank=True)
    observacoes = models.TextField("observacoes", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "avaliacao fisica"
        verbose_name_plural = "avaliacoes fisicas"
        ordering = ["-data"]
        constraints = [
            models.UniqueConstraint(fields=["aluno", "data"], name="uma_avaliacao_por_dia"),
        ]

    def __str__(self) -> str:
        return f"Avaliacao de {self.aluno} em {self.data:%d/%m/%Y}"

    @property
    def imc(self) -> Decimal:
        if not self.peso or not self.altura:
            return Decimal("0.00")
        return round(self.peso / (self.altura * self.altura), 2)

    @property
    def faixa_de_imc(self) -> str:
        imc = self.imc
        if imc == 0:
            return "sem dados"
        if imc < 18.5:
            return "abaixo do peso"
        if imc < 25:
            return "peso adequado"
        if imc < 30:
            return "sobrepeso"
        return "obesidade"

    def medidas_legiveis(self) -> list[tuple[str, Decimal]]:
        return [
            (rotulo, self.medidas.get(chave))
            for chave, rotulo in MEDIDAS
            if (self.medidas or {}).get(chave)
        ]
