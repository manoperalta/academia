"""Telas do professor: agenda, turma, treinos, alunos, avaliacoes e comissoes.

O portao de entrada e o proprio perfil de professor (nao a matriz de modulos do painel): quem nao tem
``professor.Professor`` vinculado na rede ativa recebe 403. Assim o professor entra no painel com o
papel dele e nao enxerga a operacao da unidade.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from agendamento.models import Agendamento
from painel.models import Painel
from painel_do_professor import servicos
from painel_do_professor.models import OcorrenciaDaTurma
from painel_do_professor.servicos import ErroDoProfessor
from professores.models import Professor
from treinos import servicos as servicos_de_treino
from treinos.models import AvaliacaoFisica, Treino
from treinos.servicos import ErroDeTreino
from usuarios.models import Usuario


class ContextoDoProfessorMixin(LoginRequiredMixin):
    """Garante sessao e perfil de professor na rede ativa."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        rede = getattr(request, "rede", None)
        self.professor = servicos.professor_do_usuario(request.user, rede=rede)
        if self.professor is None:
            raise PermissionDenied("Esta area e do professor.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["professor"] = self.professor
        return contexto


class MinhaAgendaView(ContextoDoProfessorMixin, TemplateView):
    template_name = "professor/agenda.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        dia = self.request.GET.get("dia")
        data_escolhida = timezone.localdate()
        if dia:
            try:
                data_escolhida = timezone.datetime.strptime(dia, "%Y-%m-%d").date()
            except ValueError:
                data_escolhida = timezone.localdate()
        contexto["agenda"] = servicos.agenda_do_dia(self.professor, data_escolhida)
        contexto["semana"] = servicos.semana_do_professor(self.professor)
        contexto["dia_escolhido"] = data_escolhida
        return contexto


class MinhaTurmaView(ContextoDoProfessorMixin, DetailView):
    template_name = "professor/turma.html"
    context_object_name = "turma"

    def get_queryset(self):
        return Painel.todos.filter(
            pk=self.kwargs["pk"],
            responsavel=self.professor.user,
            rede=self.professor.rede,
            arquivado_em__isnull=True,
        ).select_related("unidade")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        turma = self.object
        contexto["aulas"] = [item.aula for item in turma.itens.select_related("aula")]
        contexto["agendamentos"] = Agendamento.todos.filter(
            painel=turma, arquivado_em__isnull=True
        ).select_related("aluno")
        contexto["ocorrencias"] = servicos.ocorrencias_da_turma(turma)
        contexto["tipos_de_ocorrencia"] = OcorrenciaDaTurma.Tipo.choices
        contexto["capacidade"] = turma.numero_de_user
        return contexto


class ChamadaView(ContextoDoProfessorMixin, View):
    """Fecha a chamada da turma de uma vez."""

    def post(self, request, pk: int, *args, **kwargs):
        turma = get_object_or_404(
            Painel.todos.filter(
                pk=pk,
                responsavel=self.professor.user,
                rede=self.professor.rede,
                arquivado_em__isnull=True,
            )
        )
        presencas = {
            chave.replace("aluno_", ""): valor
            for chave, valor in request.POST.items()
            if chave.startswith("aluno_")
        }
        try:
            resultado = servicos.chamada_do_dia(
                turma=turma, professor=self.professor, presencas=presencas
            )
        except ErroDoProfessor as erro:
            messages.error(request, str(erro))
        else:
            messages.success(
                request, f"Chamada registrada para {resultado['atualizados']} aluno(s)."
            )
        return redirect("professor:turma", pk=pk)


class OcorrenciaView(ContextoDoProfessorMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        turma = get_object_or_404(
            Painel.todos.filter(
                pk=pk,
                responsavel=self.professor.user,
                rede=self.professor.rede,
                arquivado_em__isnull=True,
            )
        )
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=turma.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno da ocorrencia.")
            return redirect("professor:turma", pk=pk)
        try:
            servicos.registrar_ocorrencia(
                turma=turma,
                aluno=aluno,
                professor=self.professor,
                tipo=request.POST.get("tipo", "observacao"),
                descricao=request.POST.get("descricao", ""),
            )
        except ErroDoProfessor as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Ocorrencia registrada.")
        return redirect("professor:turma", pk=pk)


class SubstituicaoView(ContextoDoProfessorMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        turma = get_object_or_404(
            Painel.todos.filter(
                pk=pk,
                responsavel=self.professor.user,
                rede=self.professor.rede,
                arquivado_em__isnull=True,
            )
        )
        substituto = Professor.todos.filter(
            pk=request.POST.get("substituto"), rede=turma.rede
        ).first()
        if substituto is None:
            messages.error(request, "Escolha o professor que vai assumir.")
            return redirect("professor:turma", pk=pk)
        try:
            servicos.registrar_substituicao(
                turma=turma, substituto=substituto, motivo=request.POST.get("motivo", "")
            )
        except ErroDoProfessor as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Turma passou para {substituto.nome}.")
            return redirect("professor:agenda")
        return redirect("professor:turma", pk=pk)


class SubstituicoesDisponiveisMixin:
    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["outros_professores"] = Professor.todos.filter(
            rede=self.professor.rede, status_prof="Ativo"
        ).exclude(pk=self.professor.pk)
        return contexto


class MeusTreinosView(SubstituicoesDisponiveisMixin, ContextoDoProfessorMixin, ListView):
    template_name = "professor/treinos.html"
    context_object_name = "treinos"
    paginate_by = 25

    def get_queryset(self):
        return Treino.objects.filter(
            professor=self.professor, rede=self.professor.rede
        ).select_related("aluno")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["alunos"] = servicos.meus_alunos(self.professor)
        contexto["objetivos"] = Treino.Objetivo.choices
        return contexto


class PrescreverTreinoView(ContextoDoProfessorMixin, View):
    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=self.professor.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno do treino.")
            return redirect("professor:treinos")
        try:
            treino = servicos_de_treino.prescrever_treino(
                aluno=aluno,
                professor=self.professor,
                nome=request.POST.get("nome", ""),
                objetivo=request.POST.get("objetivo") or "condicionamento",
                observacoes=request.POST.get("observacoes", ""),
            )
        except ErroDeTreino as erro:
            messages.error(request, str(erro))
            return redirect("professor:treinos")
        messages.success(request, "Treino prescrito. Agora inclua os exercicios.")
        return redirect("professor:treino", pk=treino.pk)


class TreinoDoProfessorView(ContextoDoProfessorMixin, DetailView):
    template_name = "professor/treino.html"
    context_object_name = "treino"

    def get_queryset(self):
        return Treino.objects.filter(
            professor=self.professor, rede=self.professor.rede
        ).select_related("aluno")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["exercicios"] = self.object.exercicios.select_related("aula")
        contexto["aulas_disponiveis"] = (
            self.object.rede.aulas_set.filter(arquivado_em__isnull=True)[:200]
            if hasattr(self.object.rede, "aulas_set")
            else []
        )
        contexto["progressos"] = {
            exercicio.pk: servicos_de_treino.progresso_do_exercicio(exercicio)
            for exercicio in self.object.exercicios.all()
        }
        return contexto


class AdicionarExercicioView(ContextoDoProfessorMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        treino = get_object_or_404(
            Treino.objects.filter(pk=pk, professor=self.professor, rede=self.professor.rede)
        )
        try:
            servicos_de_treino.adicionar_exercicio(
                treino=treino,
                nome=request.POST.get("nome", ""),
                series=int(request.POST.get("series") or 3),
                repeticoes=request.POST.get("repeticoes") or "12",
                carga_sugerida=request.POST.get("carga_sugerida") or 0,
                descanso_segundos=int(request.POST.get("descanso_segundos") or 60),
            )
        except (ErroDeTreino, ValueError) as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Exercicio incluido.")
        return redirect("professor:treino", pk=pk)


class DuplicarTreinoView(ContextoDoProfessorMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        treino = get_object_or_404(
            Treino.objects.filter(pk=pk, professor=self.professor, rede=self.professor.rede)
        )
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=self.professor.rede).first()
        copia = servicos_de_treino.duplicar_treino(treino=treino, aluno=aluno)
        messages.success(request, "Treino copiado como rascunho.")
        return redirect("professor:treino", pk=copia.pk)


class MeusAlunosView(ContextoDoProfessorMixin, ListView):
    template_name = "professor/alunos.html"
    context_object_name = "alunos"
    paginate_by = 25

    def get_queryset(self):
        return servicos.meus_alunos(self.professor)


class AlunoDoProfessorView(ContextoDoProfessorMixin, DetailView):
    template_name = "professor/aluno.html"
    context_object_name = "aluno"

    def get_queryset(self):
        permitidos = servicos.meus_alunos(self.professor)
        return Usuario.todos.filter(pk__in=[aluno.pk for aluno in permitidos])

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = self.object
        from usuarios.models import FichaSaude

        contexto["ficha"] = FichaSaude.todos.filter(usuario=aluno).first()
        contexto["resumo"] = servicos_de_treino.resumo_do_aluno(aluno)
        contexto["frequencia"] = servicos.frequencia_do_aluno(aluno)
        contexto["treinos"] = Treino.objects.filter(aluno=aluno, professor=self.professor)
        contexto["avaliacoes"] = servicos.avaliacoes_do_aluno(aluno)
        contexto["evolucao"] = servicos_de_treino.evolucao_do_aluno(aluno)
        contexto["ocorrencias"] = OcorrenciaDaTurma.objects.filter(
            aluno=aluno, professor=self.professor
        )[:10]
        return contexto


class MinhasAvaliacoesView(ContextoDoProfessorMixin, TemplateView):
    template_name = "professor/avaliacoes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["avaliacoes"] = AvaliacaoFisica.objects.filter(
            avaliador=self.professor
        ).select_related("aluno")[:50]
        contexto["alunos"] = servicos.meus_alunos(self.professor)
        return contexto


class RegistrarAvaliacaoView(ContextoDoProfessorMixin, View):
    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=self.professor.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno.")
            return redirect("professor:avaliacoes")
        medidas = {
            chave: request.POST.get(chave)
            for chave in (
                "cintura",
                "quadril",
                "peito",
                "braco",
                "coxa",
                "panturrilha",
                "ombro",
                "abdomen",
            )
            if request.POST.get(chave)
        }
        try:
            servicos_de_treino.registrar_avaliacao(
                aluno=aluno,
                peso=request.POST.get("peso") or 0,
                altura=request.POST.get("altura") or 0,
                percentual_de_gordura=request.POST.get("percentual_de_gordura") or 0,
                massa_muscular=request.POST.get("massa_muscular") or 0,
                medidas=medidas,
                avaliador=self.professor,
                observacoes=request.POST.get("observacoes", ""),
            )
        except ErroDeTreino as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Avaliacao registrada.")
        return redirect("professor:avaliacoes")


class MinhasComissoesView(ContextoDoProfessorMixin, TemplateView):
    template_name = "professor/comissoes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["comissoes"] = servicos.minhas_comissoes(self.professor)
        return contexto
