"""Mixins de CBV obrigatorios no projeto (PRD secao 19.3)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.generic.base import ContextMixin

from core.context import rede_atual, unidade_atual
from core.papeis import PAPEIS_DA_REDE, Papel
from core.papeis import StatusRede as _StatusRede


def impersonando_suporte(request) -> bool:
    """True quando a requisicao esta dentro de um acesso de suporte auditado."""
    if not hasattr(request, "session"):
        return False
    return bool(request.session.get("impersonacao_id"))


def papeis_do_usuario(usuario, rede=None):
    """Papeis do usuario na rede informada (ou na rede do contexto)."""
    if not usuario or not usuario.is_authenticated:
        return set()
    rede = rede or rede_atual()
    if rede is None:
        return set()
    if usuario.is_superuser:
        return {Papel.SUPERADMIN_PLATAFORMA}
    return set(usuario.vinculos.filter(rede=rede, ativo=True).values_list("papel", flat=True))


class RedeRequiredMixin:
    """Garante que a requisicao tem rede no contexto e que o usuario tem vinculo."""

    papeis_permitidos: tuple = ()

    def dispatch(self, request, *args, **kwargs):
        rede = getattr(request, "rede", None) or rede_atual()
        if rede is None:
            messages.error(request, "Nao foi possivel identificar a academia desta sessao.")
            return redirect("login")
        vinculo = None
        if request.user.is_authenticated:
            papeis = papeis_do_usuario(request.user, rede)
            vinculo = bool(papeis)
            if not papeis and not request.user.is_superuser and not impersonando_suporte(request):
                raise PermissionDenied("Voce nao tem vinculo com esta academia.")
            if self.papeis_permitidos and not (
                set(self.papeis_permitidos).intersection(papeis) or request.user.is_superuser
            ):
                raise PermissionDenied("Seu papel nao permite acessar esta tela.")
        self.rede = rede
        self.vinculo_existe = vinculo
        return super().dispatch(request, *args, **kwargs)


class EscritaPermitidaMixin:
    """Bloqueia escrita conforme status comercial da rede (inadimplencia/suspensao)."""

    def dispatch(self, request, *args, **kwargs):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            rede = getattr(request, "rede", None) or rede_atual()
            if rede is not None and rede.status in {
                _StatusRede.SOMENTE_LEITURA,
                _StatusRede.SUSPENSO,
                _StatusRede.CANCELADO,
            }:
                raise PermissionDenied("A conta desta academia esta somente leitura no momento.")
        return super().dispatch(request, *args, **kwargs)


class UnidadeScopedMixin:
    """Aplica o recorte de unidade nas listagens (rede inteira apenas para papeis de rede)."""

    filtro_unidade = True

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = getattr(self.request, "user", None)
        papeis = papeis_do_usuario(usuario) if usuario else set()
        if self.filtro_unidade and not PAPEIS_DA_REDE.intersection(papeis):
            unidade = getattr(self.request, "unidade", None) or unidade_atual()
            if unidade is not None:
                from django.db.models import Q

                qs = qs.filter(Q(unidade_id=unidade.pk) | Q(unidade__isnull=True))
        return qs


class AuditMixin:
    """Registra quem criou/alterou (a trilha completa fica em api.RegistroAuditoria)."""

    def form_valid(self, form):
        usuario = getattr(self.request, "user", None)
        if (
            usuario
            and usuario.is_authenticated
            and not form.instance.pk
            and hasattr(form.instance, "criado_por_id")
        ):
            form.instance.criado_por = usuario
        return super().form_valid(form)


class SoftDeleteMixin:
    """DeleteView passa a arquivar em vez de excluir."""

    def form_valid(self, form):
        sucesso_url = self.get_success_url()
        self.object = self.get_object()
        self.object.arquivar()
        messages.success(self.request, "Registro arquivado. Voce pode restaura-lo depois.")
        return redirect(sucesso_url)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.arquivar()
        messages.success(request, "Registro arquivado. Voce pode restaura-lo depois.")
        return redirect(self.get_success_url())


class HTMXMixin(ContextMixin):
    """Marca o contexto para o template responder parcial quando vier do HTMX."""

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["htmx"] = bool(getattr(self.request, "htmx", False)) or (
            self.request.headers.get("HX-Request") == "true"
        )
        return contexto

    def get_template_names(self):
        if self.get_context_data().get("htmx"):
            nomes = super().get_template_names()
            nome = nomes[0]
            return [nome.replace(".html", "_parcial.html"), *nomes]
        return super().get_template_names()
