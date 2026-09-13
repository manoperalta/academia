"""Telas legadas de professor: apontam para o painel (fonte unica de cadastro).

Escolha de projeto: o cadastro de professor e do **painel**, com o modulo ``PROFESSORES`` na matriz
de permissoes -- administrador da rede e gestor da unidade. Antes existia aqui um ``professor_create``
que so exigia estar logado, o que deixava qualquer aluno criar professor.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Professor


@login_required
def professor_list(request):
    """Atalho para a lista do painel (escopada por rede)."""
    return redirect("gestao:professores")


@login_required
def professor_create(request):
    """Atalho para o cadastro do painel (la a permissao e checada)."""
    return redirect("gestao:professor_novo")


@login_required
def professor_update(request, pk):
    return redirect("gestao:professor_editar", pk=pk)


@login_required
def professor_delete(request, pk):
    return redirect("gestao:professor_arquivar", pk=pk)


@login_required
def complete_profile_professor(request):
    """O professor completa o proprio perfil -- mas o cadastro quem faz e o painel.

    O registro nunca e criado aqui: se nao existe professor para este acesso, a pessoa e
    encaminhada para o painel (onde admin da rede/gestor cadastram).
    """
    professor = getattr(request.user, "professor_profile", None)
    if professor is None:
        messages.error(
            request,
            "Nao existe cadastro de professor para este acesso. "
            "Peca ao administrador da rede ou ao gestor da unidade para cadastrar voce no painel.",
        )
        return redirect("gestao:professores")

    from gestao.forms import ProfessorForm as ProfessorDoPainelForm

    if request.method == "POST":
        form = ProfessorDoPainelForm(request.POST, request.FILES, instance=professor)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso.")
            return redirect("professor:agenda")
    else:
        form = ProfessorDoPainelForm(instance=professor)

    return render(request, "professores/complete_profile.html", {"form": form})


def perfil_do_professor(usuario):
    """Professor do usuario logado (ou None) -- usado por telas de perfil."""
    if not getattr(usuario, "is_authenticated", False):
        return None
    return Professor.todos.filter(user=usuario).first()
