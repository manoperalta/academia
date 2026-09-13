"""Modelos do painel do professor: ocorrencias da turma e a agenda que ele mesmo abre.

Os modelos de turma (``painel.Painel``), aula (``aulas.Aulas``), agendamento
(``agendamento.Agendamento``), treino (``treinos.Treino``) e comissao
(``remuneracao``) ja existem. Aqui fica o que faltava:

- o registro do que aconteceu com o aluno durante a aula (``OcorrenciaDaTurma``);
- a **disponibilidade** que o professor abre (dia da semana, janela, tempo do
  compromisso) e a composicao dela por aulas/videos;
- o rastro do que essa disponibilidade gerou em turmas (``TurmaMaterializada``).

Escolha de projeto: o professor nao cria horario solto. Ele descreve a
**recorrencia** (todo terca, das 19h as 21h, compromisso de 60 min) e o sistema
materializa as turmas das proximas semanas. Assim a agenda dele se mantem
sozinha e o aluno reserva horarios de verdade, com dia e hora.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel
from painel.models import Painel
from professores.models import Professor
from usuarios.models import Usuario


class OcorrenciaDaTurma(models.Model):
    """Anotacao do professor sobre o aluno na aula (dor, ausencia, evolucao, conduta)."""

    class Tipo(models.TextChoices):
        DOR_OU_LESAO = "dor_ou_lesao", "Dor ou lesao"
        AUSENCIA = "ausencia", "Ausencia"
        EVOLUCAO = "evolucao", "Evolucao"
        CONDUTA = "conduta", "Conduta"
        OBSERVACAO = "observacao", "Observacao geral"

    turma = models.ForeignKey(Painel, on_delete=models.CASCADE, related_name="ocorrencias")
    aluno = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="ocorrencias")
    professor = models.ForeignKey(
        Professor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ocorrencias_registradas",
    )
    tipo = models.CharField("tipo", max_length=15, choices=Tipo.choices, default=Tipo.OBSERVACAO)
    descricao = models.TextField("descricao")
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "ocorrencia da turma"
        verbose_name_plural = "ocorrencias da turma"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.aluno} em {self.turma}"


class SubstituicaoDeTurma(models.Model):
    """Quando o professor responsavel nao pode dar a aula e outro assume."""

    turma = models.ForeignKey(Painel, on_delete=models.CASCADE, related_name="substituicoes")
    titular = models.ForeignKey(
        Professor, on_delete=models.CASCADE, related_name="substituicoes_como_titular"
    )
    substituto = models.ForeignKey(
        Professor, on_delete=models.CASCADE, related_name="substituicoes_como_substituto"
    )
    motivo = models.CharField("motivo", max_length=200, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "substituicao de turma"
        verbose_name_plural = "substituicoes de turma"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.titular} -> {self.substituto} em {self.turma}"


class DisponibilidadeDoProfessor(TenantModel):
    """Bloco de agenda que o professor abre: quando atende, por quanto tempo e com quais aulas.

    ``duracao_minutos`` e o **tempo do compromisso**: a janela e fatiada nesse tamanho e cada
    fatia vira um horario reservavel pelo aluno.
    """

    class DiaDaSemana(models.IntegerChoices):
        SEGUNDA = 0, "Segunda-feira"
        TERCA = 1, "Terca-feira"
        QUARTA = 2, "Quarta-feira"
        QUINTA = 3, "Quinta-feira"
        SEXTA = 4, "Sexta-feira"
        SABADO = 5, "Sabado"
        DOMINGO = 6, "Domingo"

    professor = models.ForeignKey(
        Professor,
        on_delete=models.CASCADE,
        related_name="disponibilidades",
        verbose_name="professor",
    )
    nome = models.CharField(
        "nome do atendimento",
        max_length=120,
        default="Atendimento",
        help_text="O que o aluno ve ao escolher este horario (ex.: Atendimento individual).",
    )
    dia_da_semana = models.PositiveSmallIntegerField(
        "dia da semana", choices=DiaDaSemana.choices, default=DiaDaSemana.SEGUNDA
    )
    hora_inicio = models.TimeField("abre as")
    hora_fim = models.TimeField("fecha as")
    duracao_minutos = models.PositiveSmallIntegerField(
        "tempo do compromisso (minutos)",
        default=60,
        help_text="A janela e dividida nesse tempo: cada parte vira um horario agendavel.",
    )
    vagas_por_horario = models.PositiveIntegerField(
        "vagas por horario", default=1, help_text="Quantos alunos cabem em cada horario."
    )
    inicio_vigencia = models.DateField("vale a partir de", null=True, blank=True)
    fim_vigencia = models.DateField("vale ate", null=True, blank=True)
    ativo = models.BooleanField("aberta", default=True)
    observacoes = models.TextField("observacoes", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "disponibilidade do professor"
        verbose_name_plural = "disponibilidades do professor"
        ordering = ["dia_da_semana", "hora_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["professor", "dia_da_semana", "hora_inicio"],
                name="disponibilidade_unica_por_professor_dia_hora",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_dia_da_semana_display()} "
            f"{self.hora_inicio:%H:%M}-{self.hora_fim:%H:%M} ({self.professor})"
        )

    # ------------------------------------------------------------- regras do bloco
    def clean(self) -> None:
        if self.hora_inicio and self.hora_fim and self.hora_fim <= self.hora_inicio:
            raise ValidationError({"hora_fim": "O horario de fechamento tem de ser depois da abertura."})
        if self.duracao_minutos is not None and self.duracao_minutos < 1:
            raise ValidationError({"duracao_minutos": "O tempo do compromisso tem de ser positivo."})
        if (
            self.hora_inicio
            and self.hora_fim
            and self.duracao_minutos
            and self.duracao_minutos > self.janela_minutos
        ):
            raise ValidationError(
                {
                    "duracao_minutos": (
                        f"O tempo do compromisso ({self.duracao_minutos} min) e maior que a "
                        f"janela aberta ({self.janela_minutos} min)."
                    )
                }
            )
        if self.inicio_vigencia and self.fim_vigencia and self.fim_vigencia < self.inicio_vigencia:
            raise ValidationError({"fim_vigencia": "A vigencia termina antes de comecar."})

    @property
    def janela_minutos(self) -> int:
        if not (self.hora_inicio and self.hora_fim):
            return 0
        abertura = datetime.combine(datetime(2000, 1, 1), self.hora_inicio)
        fechamento = datetime.combine(datetime(2000, 1, 1), self.hora_fim)
        return int((fechamento - abertura).total_seconds() // 60)

    @property
    def sobra_minutos(self) -> int:
        """Minutos que sobram no fim da janela (nao viram horario)."""
        if not self.duracao_minutos:
            return 0
        return self.janela_minutos % self.duracao_minutos

    def horarios(self) -> list[tuple[datetime.time, datetime.time]]:
        """Fatia a janela no tempo do compromisso, na ordem."""
        if not (self.hora_inicio and self.hora_fim and self.duracao_minutos):
            return []
        fatias = []
        cursor = datetime.combine(datetime(2000, 1, 1), self.hora_inicio)
        limite = datetime.combine(datetime(2000, 1, 1), self.hora_fim)
        passo = timedelta(minutes=self.duracao_minutos)
        while cursor + passo <= limite:
            fatias.append((cursor.time(), (cursor + passo).time()))
            cursor += passo
        return fatias

    def alcanca(self, data) -> bool:
        """Se a vigencia do bloco cobre a data informada."""
        if self.inicio_vigencia and data < self.inicio_vigencia:
            return False
        return not (self.fim_vigencia and data > self.fim_vigencia)

    @property
    def total_de_aulas(self) -> int:
        """Quantas aulas (videos) compoem o compromisso -- pelo manager global (nao escopado)."""
        return AulaDaDisponibilidade.todos.filter(disponibilidade=self).count()

    def aulas_compostas(self):
        """Aulas (videos) que compoem o compromisso, na ordem definida -- manager global.

        O relacionamento reverso de um ``TenantModel`` (``self.composicao``) usa o manager com
        escopo e esconderia as linhas fora do painel da rede; aqui a chave e a propria
        disponibilidade.
        """
        return [
            item.aula
            for item in AulaDaDisponibilidade.todos.filter(disponibilidade=self)
            .select_related("aula")
            .order_by("ordem", "pk")
        ]

    def minutos_de_video(self) -> int | None:
        """Soma das duracoes conhecidas dos videos (``None`` quando nao da para saber)."""
        duracoes = [
            aula.duracao_em_minutos
            for aula in self.aulas_compostas()
            if getattr(aula, "duracao_em_minutos", None)
        ]
        return sum(duracoes) if duracoes else None


class AulaDaDisponibilidade(TenantModel):
    """Uma aula (video) dentro do compromisso do professor, com a ordem de execucao."""

    disponibilidade = models.ForeignKey(
        DisponibilidadeDoProfessor, on_delete=models.CASCADE, related_name="composicao"
    )
    aula = models.ForeignKey(
        "aulas.Aulas", on_delete=models.CASCADE, related_name="nas_disponibilidades"
    )
    ordem = models.PositiveIntegerField("ordem", default=1)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "aula da disponibilidade"
        verbose_name_plural = "aulas da disponibilidade"
        ordering = ["disponibilidade", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["disponibilidade", "aula"], name="aula_unica_por_disponibilidade"
            )
        ]

    def __str__(self) -> str:
        return f"{self.ordem}. {self.aula}"


class TurmaMaterializada(TenantModel):
    """Rastro do que a disponibilidade gerou: liga a recorrencia a turma concreta.

    Sem esse rastro, uma segunda materializacao nao saberia o que ela mesma criou -- e acabaria
    duplicando horario ou apagando turma que o gestor criou na mao.
    """

    disponibilidade = models.ForeignKey(
        DisponibilidadeDoProfessor, on_delete=models.CASCADE, related_name="turmas_geradas"
    )
    turma = models.OneToOneField(
        Painel, on_delete=models.CASCADE, related_name="origem_da_agenda"
    )
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "turma materializada"
        verbose_name_plural = "turmas materializadas"

    def __str__(self) -> str:
        return f"{self.turma} (de {self.disponibilidade})"
