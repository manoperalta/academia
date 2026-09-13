"""Telas de conta: perfil, senha, recuperacao, sessoes e suporte."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from conta import servicos
from conta.models import ChamadoDeSuporte
from conta.servicos import ErroDeConta
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo


class ContaMixin(LoginRequiredMixin):
    """Base das telas de conta: precisa de sessao e resolve o vinculo ativo."""

    def perfil_do_usuario(self, request):
        """Perfil da pessoa na rede ativa: aluno, professor ou nenhum dos dois (equipe)."""
        from professores.models import Professor
        from usuarios.models import Usuario

        rede = getattr(request, "rede", None)
        aluno = Usuario.todos.filter(user=request.user, rede=rede).first() if rede else None
        professor = Professor.todos.filter(user=request.user, rede=rede).first() if rede else None
        return {"aluno": aluno, "professor": professor}

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(self.perfil_do_usuario(self.request))
        return contexto


class MeuPerfilView(ContaMixin, TemplateView):
    """Dados de contato do usuario e o apontamento para as preferencias de aviso."""

    template_name = "conta/perfil.html"

    def post(self, request, *args, **kwargs):
        email = (request.POST.get("email") or "").strip()
        telefone = (request.POST.get("telefone") or "").strip()
        nome = (request.POST.get("nome") or "").strip()
        perfis = self.perfil_do_usuario(request)
        if email and email != request.user.email:
            request.user.email = email
            request.user.save(update_fields=["email"])
        if perfis["aluno"] is not None:
            perfil = perfis["aluno"]
            perfil.nome = nome or perfil.nome
            perfil.email_user = email or perfil.email_user
            perfil.telefone_user = telefone or perfil.telefone_user
            perfil.save(update_fields=["nome", "email_user", "telefone_user"])
        elif perfis["professor"] is not None:
            perfil = perfis["professor"]
            perfil.nome = nome or perfil.nome
            perfil.email_prof = email or perfil.email_prof
            perfil.telefone_prof = telefone or perfil.telefone_prof
            perfil.save(update_fields=["nome", "email_prof", "telefone_prof"])
        messages.success(request, "Dados atualizados.")
        return redirect("conta:perfil")


class AlterarSenhaView(PasswordChangeView):
    template_name = "conta/senha.html"
    success_url = reverse_lazy("conta:perfil")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada.")
        return super().form_valid(form)


class RecuperarSenhaView(PasswordResetView):
    template_name = "registration/password_reset_form.html"
    email_template_name = "conta/emails/password_reset_email.html"
    subject_template_name = "conta/emails/password_reset_subject.txt"
    success_url = reverse_lazy("conta:senha_redefinida")

    def form_valid(self, form):
        messages.success(
            self.request,
            "Se este e-mail estiver cadastrado, o link de redefinição chega em instantes.",
        )
        return super().form_valid(form)


class SenhaRedefinidaView(PasswordResetDoneView):
    template_name = "registration/password_reset_done.html"


class ConfirmarNovaSenhaView(PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("conta:senha_alterada")


class SenhaAlteradaView(PasswordResetCompleteView):
    template_name = "registration/password_reset_complete.html"


class SessoesAtivasView(ContaMixin, TemplateView):
    """Onde a conta esta logada agora — e como sair dos outros aparelhos."""

    template_name = "conta/sessoes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["sessoes"] = servicos.sessoes_ativas(
            self.request.user, self.request.session.session_key or ""
        )
        return contexto

    def post(self, request, *args, **kwargs):
        removidas = servicos.encerrar_outras_sessoes(
            request.user, request.session.session_key or ""
        )
        messages.success(
            request, f"{removidas} sessao(oes) encerrada(s). A sessao atual continua ativa."
        )
        return redirect("conta:sessoes")


class MeusChamadosView(ContaMixin, TemplateView):
    template_name = "conta/chamados.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        rede = getattr(self.request, "rede", None)
        contexto["chamados"] = (
            ChamadoDeSuporte.objects.filter(
                rede=rede, aberto_por=self.request.user
            ).prefetch_related("mensagens")
            if rede
            else []
        )
        contexto["categorias"] = ChamadoDeSuporte.Categoria.choices
        contexto["prioridades"] = ChamadoDeSuporte.Prioridade.choices
        return contexto

    def post(self, request, *args, **kwargs):
        rede = getattr(request, "rede", None)
        if rede is None:
            raise Http404("sem-rede-ativa")
        perfis = self.perfil_do_usuario(request)
        try:
            chamado = servicos.abrir_chamado(
                rede=rede,
                titulo=request.POST.get("titulo", ""),
                descricao=request.POST.get("descricao", ""),
                categoria=request.POST.get("categoria") or "duvida",
                prioridade=request.POST.get("prioridade") or "normal",
                aberto_por=request.user,
                unidade=getattr(perfis["aluno"] or perfis["professor"], "unidade", None),
                aluno=perfis["aluno"],
            )
        except ErroDeConta as erro:
            messages.error(request, str(erro))
            return redirect("conta:chamados")
        messages.success(request, "Chamado aberto. Você acompanha por aqui.")
        return redirect("conta:chamado", pk=chamado.pk)


class ChamadoView(ContaMixin, DetailView):
    template_name = "conta/chamado.html"
    context_object_name = "chamado"

    def get_queryset(self):
        rede = getattr(self.request, "rede", None)
        return ChamadoDeSuporte.objects.filter(rede=rede, aberto_por=self.request.user)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["mensagens_do_chamado"] = self.object.mensagens.exclude(
            interna=True
        ).select_related("autor")
        return contexto

    def post(self, request, pk: int, *args, **kwargs):
        chamado = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            servicos.responder(
                chamado=chamado, texto=request.POST.get("texto", ""), autor=request.user
            )
        except ErroDeConta as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Resposta enviada.")
        return redirect("conta:chamado", pk=chamado.pk)


class FilaDoSuporteView(PainelMixin, ListView):
    """Fila do suporte para a equipe da rede: o que esta aberto e o tempo medio de resposta."""

    modulo = Modulo.SUPORTE
    template_name = "conta/fila_suporte.html"
    context_object_name = "chamados"
    paginate_by = 50

    def get_queryset(self):
        return (
            ChamadoDeSuporte.objects.filter(rede=self.request.rede)
            .exclude(
                situacao__in=[
                    ChamadoDeSuporte.Situacao.RESOLVIDO,
                    ChamadoDeSuporte.Situacao.FECHADO,
                ]
            )
            .select_related("unidade", "aberto_por", "aluno")
            .order_by("criado_em")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_do_suporte(self.request.rede)
        return contexto


class ResponderChamadoView(EdicaoMixin, View):
    modulo = Modulo.SUPORTE

    def post(self, request, pk: int, *args, **kwargs):
        chamado = get_object_or_404(ChamadoDeSuporte.objects.filter(rede=request.rede), pk=pk)
        acao = request.POST.get("acao", "responder")
        try:
            if acao == "situacao":
                servicos.mudar_situacao(
                    chamado=chamado, situacao=request.POST.get("situacao"), responsavel=request.user
                )
                messages.success(request, "Situação do chamado atualizada.")
            else:
                servicos.responder(
                    chamado=chamado,
                    texto=request.POST.get("texto", ""),
                    autor=request.user,
                    interna=request.POST.get("interna") == "on",
                )
                messages.success(request, "Resposta registrada.")
        except ErroDeConta as erro:
            messages.error(request, str(erro))
        return redirect("conta:fila_suporte")
