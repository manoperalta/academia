"""Telas do aluno para treino, execucao e evolucao.

O aluno ve e executa o que o professor prescreveu; a prescricao em si e da area do professor.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from treinos import servicos
from treinos.models import ExercicioDoTreino, Treino
from treinos.servicos import ErroDeTreino


def aluno_da_sessao(request):
    from area_do_aluno.views import aluno_da_sessao as resolver

    return resolver(request)


class MeusTreinosDoAlunoView(ListView):
    template_name = "treinos/meus_treinos.html"
    context_object_name = "treinos"

    def get_queryset(self):
        aluno = aluno_da_sessao(self.request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        return Treino.objects.filter(aluno=aluno).exclude(situacao=Treino.Situacao.CANCELADO)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["aluno"] = aluno_da_sessao(self.request)
        return contexto


class TreinoDoAlunoView(DetailView):
    template_name = "treinos/meu_treino.html"
    context_object_name = "treino"

    def get_queryset(self):
        aluno = aluno_da_sessao(self.request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        return Treino.objects.filter(aluno=aluno)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["aluno"] = aluno_da_sessao(self.request)
        contexto["exercicios"] = self.object.exercicios.select_related("aula")
        contexto["progressos"] = {
            exercicio.pk: servicos.progresso_do_exercicio(exercicio)
            for exercicio in self.object.exercicios.all()
        }
        return contexto


class RegistrarExecucaoView(View):
    def post(self, request, pk: int, *args, **kwargs):
        aluno = aluno_da_sessao(request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        exercicio = get_object_or_404(ExercicioDoTreino.objects.filter(treino__aluno=aluno), pk=pk)
        try:
            servicos.registrar_execucao(
                exercicio=exercicio,
                carga=request.POST.get("carga") or 0,
                repeticoes=request.POST.get("repeticoes", ""),
                esforco_percebido=int(request.POST.get("esforco_percebido") or 0),
                observacoes=request.POST.get("observacoes", ""),
            )
        except (ErroDeTreino, ValueError) as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Execução registrada.")
        return redirect("treinos:meu_treino", pk=exercicio.treino_id)


class MinhaEvolucaoView(TemplateView):
    template_name = "treinos/minha_evolucao.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = aluno_da_sessao(self.request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        contexto["aluno"] = aluno
        contexto["evolucao"] = servicos.evolucao_do_aluno(aluno)
        return contexto
