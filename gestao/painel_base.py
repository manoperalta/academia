"""Base reutilizavel para telas novas do painel (fase 8)."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView


class PaginaDoPainel(TemplateView):
    """Pagina simples do painel (dashboard interno)."""

    modulo = None
    titulo = ""
    subtitulo = ""
    template_name = ""
    nivel_minimo = "ver"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.setdefault("titulo", self.titulo)
        contexto.setdefault("subtitulo", self.subtitulo)
        return contexto


class FormularioDoPainel(View):
    """GET mostra o formulario, POST salva — com o contexto de rede/unidade aplicado."""

    form_class = None
    template_name = "gestao/formulario.html"
    titulo = ""
    subtitulo = ""
    sucesso_url = ""
    modulo = None
    nivel_minimo = "editar"
    mensagem_de_sucesso = "Registro salvo."
    usar_formset = False

    def get_objeto(self):
        return None

    def get_form(self, dados=None):
        objeto = self.get_objeto()
        return (
            self.form_class(dados, instance=objeto)
            if objeto is not None
            else self.form_class(dados)
        )

    def get_context_data(self, form):
        return {
            "form": form,
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "sucesso_url": self.sucesso_url,
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data(self.get_form()))

    def post(self, request, *args, **kwargs):
        form = self.get_form(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, self.get_context_data(form))
        self.salvar(form, request)
        messages.success(request, self.mensagem_de_sucesso)
        return redirect(self.sucesso_url or request.path)

    def salvar(self, form, request):
        objeto = form.save(commit=False)
        rede = getattr(request, "rede", None)
        if hasattr(objeto, "rede_id") and not getattr(objeto, "rede_id", None) and rede is not None:
            objeto.rede = rede
        unidade = getattr(request, "unidade", None)
        if (
            hasattr(objeto, "unidade_id")
            and not getattr(objeto, "unidade_id", None)
            and unidade is not None
        ):
            objeto.unidade = unidade
        objeto.save()
        form.save_m2m()
        return objeto
