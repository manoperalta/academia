"""Telas de professor do dashboard -- mesma casca do cadastro de aluno (Bootstrap).

Historico: ate 14/09/2026 estas rotas apenas redirecionavam para o painel de gestao
(Tailwind), o que fazia "adicionar professor" parecer outro sistema. O motivo do redirect
era de seguranca -- antes qualquer pessoa logada criava professor --, e essa protecao foi
**preservada**: cada tela exige o modulo ``PROFESSORES`` na matriz de permissoes, alem de
respeitar o status comercial da conta (somente leitura/suspensa).
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView, View

from core.mixins import EscritaPermitidaMixin, RedeRequiredMixin
from core.models import VinculoUsuario
from core.papeis import Papel
from gestao.permissoes import Modulo, pode

from . import servicos
from .forms import ProfessorForm, ProfessorProfileForm
from .models import Professor


class CadastroDeProfessorMixin(RedeRequiredMixin, EscritaPermitidaMixin, LoginRequiredMixin):
    """Rede no contexto, conta em somente leitura respeitada e modulo liberado ao papel."""

    modulo = Modulo.PROFESSORES
    nivel_minimo = "ver"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not pode(
            request.user,
            self.modulo,
            self.nivel_minimo,
            rede=getattr(request, "rede", None),
            unidade=getattr(request, "unidade", None),
        ):
            raise PermissionDenied("Seu papel nao permite acessar o cadastro de professores.")
        return super().dispatch(request, *args, **kwargs)


class EscritaDeProfessorMixin(CadastroDeProfessorMixin):
    """Quem cadastra/edita precisa do nivel de edicao no modulo."""

    nivel_minimo = "editar"


class ProfessorListView(CadastroDeProfessorMixin, ListView):
    model = Professor
    template_name = "professores/professor_list.html"
    context_object_name = "professores"
    paginate_by = 50

    def get_queryset(self):
        consulta = (
            Professor.objects.filter(arquivado_em__isnull=True)
            .select_related("user")
            .order_by("nome")
        )
        termo = (self.request.GET.get("q") or "").strip()
        if termo:
            consulta = consulta.filter(
                Q(nome__icontains=termo)
                | Q(cpf_cnpj_prof__icontains=termo)
                | Q(email_prof__icontains=termo)
            )
        unidade = self.request.GET.get("unidade") or ""
        if unidade.isdigit():
            consulta = consulta.filter(
                user__vinculos__unidade_id=int(unidade), user__vinculos__ativo=True
            ).distinct()
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        professores = list(contexto["professores"])
        identificadores = [p.user_id for p in professores if p.user_id]
        nomes: dict[int, list[str]] = {}
        if identificadores:
            vinculos = VinculoUsuario.todos.filter(
                usuario_id__in=identificadores, papel=Papel.PROFESSOR, ativo=True
            ).values_list("usuario_id", "unidade__nome")
            for usuario_id, nome in vinculos:
                nomes.setdefault(usuario_id, []).append(nome or "")
        for professor in professores:
            professor.unidades_nomes = nomes.get(professor.user_id, [])
        contexto["professores"] = professores
        contexto["total"] = len(professores)
        contexto["q"] = self.request.GET.get("q", "")
        contexto["unidades"] = servicos.unidades_da_rede(getattr(self.request, "rede", None))
        contexto["unidade_atual"] = self.request.GET.get("unidade", "")
        return contexto


class ProfessorCreateView(EscritaDeProfessorMixin, CreateView):
    model = Professor
    form_class = ProfessorForm
    template_name = "professores/professor_form.html"
    success_url = reverse_lazy("professor_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["rede"] = getattr(self.request, "rede", None)
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["title"] = "Novo Professor"
        return contexto

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, f"Professor {self.object.nome} cadastrado com sucesso!")
        if getattr(form, "senha_temporaria", ""):
            messages.info(
                self.request,
                f"Senha inicial gerada para {self.object.email_prof}: {form.senha_temporaria}",
            )
        return resposta


class ProfessorUpdateView(EscritaDeProfessorMixin, UpdateView):
    model = Professor
    form_class = ProfessorForm
    template_name = "professores/professor_form.html"
    success_url = reverse_lazy("professor_list")

    def get_queryset(self):
        return Professor.objects.select_related("user").filter(arquivado_em__isnull=True)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["rede"] = getattr(self.request, "rede", None)
        return kwargs

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["title"] = "Editar Professor"
        return contexto

    def form_valid(self, form):
        resposta = super().form_valid(form)
        messages.success(self.request, "Professor atualizado com sucesso!")
        return resposta


class ProfessorDeleteView(EscritaDeProfessorMixin, View):
    """Arquiva (soft delete) o professor -- as turmas e a agenda ficam no historico."""

    template_name = "professores/professor_confirm_delete.html"

    def get_professor(self, pk):
        return Professor.objects.filter(pk=pk).first()

    def get(self, request, pk):
        professor = self.get_professor(pk)
        if professor is None:
            messages.error(request, "Professor nao encontrado nesta academia.")
            return redirect("professor_list")
        return render(request, self.template_name, {"professor": professor})

    def post(self, request, pk):
        professor = self.get_professor(pk)
        if professor is None:
            messages.error(request, "Professor nao encontrado nesta academia.")
            return redirect("professor_list")
        if professor.arquivado_em is None:
            professor.arquivado_em = timezone.now()
            professor.save(update_fields=["arquivado_em"])
        messages.success(request, f"Professor {professor.nome} arquivado com sucesso!")
        return redirect("professor_list")


@login_required
def complete_profile_professor(request):
    """O professor completa o proprio perfil -- o cadastro continua sendo do dashboard.

    O registro nunca e criado aqui: se nao existe professor para este acesso, a pessoa e
    encaminhada para a area do professor.
    """
    professor = getattr(request.user, "professor_profile", None)
    if professor is None:
        messages.error(
            request,
            "Nao existe cadastro de professor para este acesso. "
            "Peca ao administrador da rede ou ao gestor da unidade para cadastrar voce.",
        )
        return redirect("professor:agenda")

    if request.method == "POST":
        form = ProfessorProfileForm(request.POST, request.FILES, instance=professor)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("professor:agenda")
    else:
        form = ProfessorProfileForm(instance=professor)

    return render(request, "professores/complete_profile.html", {"form": form})


def perfil_do_professor(usuario):
    """Professor do usuario logado (ou None) -- usado por telas de perfil."""
    if not getattr(usuario, "is_authenticated", False):
        return None
    return Professor.todos.filter(user=usuario).first()
