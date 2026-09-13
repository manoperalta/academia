"""Formulario da agenda do professor: abre o horario, define o tempo e seleciona as aulas.

A composicao do compromisso e feita aqui: cada aula equivale a um video e o conjunto delas fecha o
tempo que o professor disponibilizou (o sistema avisa quando nao fecha; nao impede -- decisao de
produto).
"""

from __future__ import annotations

from django import forms

from aulas.models import Aulas

from .models import DisponibilidadeDoProfessor

CAMPO = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 "
    "shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
)


class EstiloDoProfessorMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxSelectMultiple):
                campo.widget.attrs["class"] = "space-y-1 text-sm"
            else:
                campo.widget.attrs["class"] = CAMPO


class DisponibilidadeForm(EstiloDoProfessorMixin, forms.ModelForm):
    """Bloco de agenda do professor, com as aulas que compoem o compromisso."""

    aulas = forms.ModelMultipleChoiceField(
        label="Aulas que compoem o compromisso",
        queryset=Aulas.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Cada aula equivale a um video. Escolha as que fecham o tempo do compromisso -- "
            "os videos ficam visiveis para o aluno junto da descricao."
        ),
    )

    class Meta:
        model = DisponibilidadeDoProfessor
        fields = [
            "nome",
            "dia_da_semana",
            "hora_inicio",
            "hora_fim",
            "duracao_minutos",
            "vagas_por_horario",
            "inicio_vigencia",
            "fim_vigencia",
            "observacoes",
        ]
        widgets = {
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
            "inicio_vigencia": forms.DateInput(attrs={"type": "date"}),
            "fim_vigencia": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, professor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.professor = professor
        consulta = Aulas.objects.none()
        if professor is not None:
            consulta = (
                Aulas.todos.filter(rede=professor.rede, arquivado_em__isnull=True)
                .order_by("categorias_exercicios", "nome")
            )
        self.fields["aulas"].queryset = consulta
        if self.instance and self.instance.pk:
            self.fields["aulas"].initial = [aula.pk for aula in self.instance.aulas_compostas()]

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("hora_inicio"), dados.get("hora_fim")
        duracao = dados.get("duracao_minutos")
        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", "O horario de fechamento tem de ser depois da abertura.")
        elif inicio and fim and duracao:
            janela = (fim.hour * 60 + fim.minute) - (inicio.hour * 60 + inicio.minute)
            if duracao > janela:
                self.add_error(
                    "duracao_minutos",
                    f"O tempo do compromisso ({duracao} min) e maior que a janela aberta "
                    f"({janela} min).",
                )
        return dados
