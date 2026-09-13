"""Modelos do painel do professor: as ocorrencias que ele registra na turma.

Os modelos de turma (``painel.Painel``), aula (``aulas.Aulas``), agendamento
(``agendamento.Agendamento``), treino (``treinos.Treino``) e comissao
(``remuneracao``) ja existem — aqui fica so o que faltava: o registro do que
aconteceu com o aluno durante a aula.
"""

from __future__ import annotations

from django.db import models

from painel.models import Painel
from professores.models import Professor
from usuarios.models import Usuario


class OcorrenciaDaTurma(models.Model):
    """Anotacao do professor sobre o aluno na aula (dor, ausencia, evoluicao, conduta)."""

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
