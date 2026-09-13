"""Area do aluno (PWA): inicio, check-in, pontos e pesquisas."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from area_do_aluno.models import CheckinDoAluno
from area_do_aluno.servicos import ErroDeCheckin, registrar_checkin, resumo_do_aluno

NOME_DO_APP = "Academia"
COR_PADRAO = "#0f172a"


def aluno_da_sessao(request):
    """O perfil de aluno do usuario logado (o login e o mesmo do app)."""
    from usuarios.models import Usuario

    if not request.user.is_authenticated:
        return None
    return Usuario.todos.filter(user=request.user).first()


def marca_do_cliente(request) -> dict:
    """Cores e nome da rede para o PWA sair com a marca do cliente."""
    inicio = {"nome": NOME_DO_APP, "cor": COR_PADRAO}
    rede = getattr(request, "rede", None)
    if rede is None:
        return inicio
    inicio["nome"] = rede.nome
    identidade = getattr(rede, "identidadevisual", None)
    if identidade is not None:
        for campo in ("cor_primaria", "cor_principal", "cor", "primaria"):
            valor = getattr(identidade, campo, None)
            if valor:
                inicio["cor"] = valor
                break
    return inicio


class InicioDoAlunoView(LoginRequiredMixin, TemplateView):
    template_name = "area_do_aluno/inicio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = aluno_da_sessao(self.request)
        contexto["marca"] = marca_do_cliente(self.request)
        contexto["aluno"] = aluno
        contexto["resumo"] = resumo_do_aluno(aluno) if aluno else None
        contexto["unidades"] = (
            __import__("core.models", fromlist=["Unidade"]).Unidade.objects.filter(
                rede=aluno.rede, status="ativa"
            )
            if aluno
            else []
        )
        return contexto


class CheckinView(LoginRequiredMixin, View):
    """Check-in pelo proprio aluno: vale em qualquer unidade da rede (RF-RED-003)."""

    def post(self, request, *args, **kwargs):
        from core.models import Unidade

        aluno = aluno_da_sessao(request)
        if aluno is None:
            messages.error(request, "Seu usuario nao esta vinculado a uma academia.")
            return redirect("aluno:inicio")
        unidade = Unidade.objects.filter(pk=request.POST.get("unidade")).first() or aluno.unidade
        try:
            checkin, resultado = registrar_checkin(aluno, unidade)
        except ErroDeCheckin as erro:
            messages.error(request, str(erro))
            return redirect("aluno:inicio")
        if resultado.get("pontuou"):
            messages.success(
                request,
                f"Check-in registrado! +{resultado['pontos']} pontos "
                f"(total {resultado['total']}, nivel {resultado['nivel']}).",
            )
        else:
            messages.success(request, "Check-in registrado!")
        for conquista in resultado.get("conquistas", []):
            messages.success(
                request, f"Conquista desbloqueada: {conquista['icone']} {conquista['nome']}"
            )
        return redirect("aluno:inicio")


class PontosView(LoginRequiredMixin, TemplateView):
    template_name = "area_do_aluno/pontos.html"

    def get_context_data(self, **kwargs):
        from gamificacao.servicos import ranking, saldo_do_aluno

        contexto = super().get_context_data(**kwargs)
        aluno = aluno_da_sessao(self.request)
        contexto["marca"] = marca_do_cliente(self.request)
        contexto["aluno"] = aluno
        contexto["saldo"] = saldo_do_aluno(aluno) if aluno else None
        contexto["ranking"] = ranking(
            rede=getattr(aluno, "rede", None), unidade=getattr(aluno, "unidade", None)
        )
        contexto["meus_checkins"] = CheckinDoAluno.objects.filter(aluno=aluno)[:10] if aluno else []
        return contexto


class PesquisaDoAlunoView(LoginRequiredMixin, View):
    """Responde a pesquisa (NPS) e ja pontua na gamificacao."""

    template_name = "area_do_aluno/pesquisa.html"

    def get(self, request, *args, **kwargs):
        from nps.models import Pesquisa

        aluno = aluno_da_sessao(request)
        pesquisa = Pesquisa.objects.filter(pk=kwargs.get("pk")).first()
        if aluno is None or pesquisa is None or not pesquisa.aceita_resposta():
            messages.info(request, "Pesquisa indisponivel no momento.")
            return redirect("aluno:inicio")
        notas = range(0, 11) if pesquisa.tipo == "nps" else range(1, 6)
        return render(
            request,
            self.template_name,
            {
                "marca": marca_do_cliente(request),
                "aluno": aluno,
                "pesquisa": pesquisa,
                "notas_possiveis": list(notas),
            },
        )

    def post(self, request, *args, **kwargs):
        from nps.models import Pesquisa
        from nps.servicos import ErroDePesquisa, registrar_resposta

        aluno = aluno_da_sessao(request)
        pesquisa = Pesquisa.objects.filter(pk=kwargs.get("pk")).first()
        if aluno is None or pesquisa is None:
            messages.error(request, "Pesquisa indisponivel.")
            return redirect("aluno:inicio")
        try:
            registrar_resposta(
                pesquisa, aluno, request.POST.get("nota"), request.POST.get("comentario", "")
            )
        except ErroDePesquisa as erro:
            messages.error(request, str(erro))
            return redirect("aluno:pesquisa", pk=pesquisa.pk)
        messages.success(request, "Obrigado pela resposta! +pontos na sua conta.")
        return redirect("aluno:inicio")


def manifest(request):
    """Manifest do PWA com a marca da rede (RF: PWA do aluno com a marca)."""
    marca = marca_do_cliente(request)
    return JsonResponse(
        {
            "name": f"{marca['nome']} - area do aluno",
            "short_name": marca["nome"][:12],
            "start_url": "/aluno/",
            "scope": "/aluno/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": marca["cor"],
            "description": "Treinos, check-in, pontos e pesquisas do aluno.",
            "icons": [
                {
                    "src": "/aluno/icone-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
                {"src": "/aluno/icone-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        }
    )


def service_worker(request):
    """Service worker na raiz do escopo: cache das telas do aluno (funciona offline)."""
    corpo = """const CACHE = 'aluno-v1';
const ESSENCIAIS = ['/aluno/', '/aluno/pontos/', '/aluno/manifest.webmanifest'];
self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ESSENCIAIS)));
  self.skipWaiting();
});
self.addEventListener('activate', (evento) => {
  evento.waitUntil(caches.keys().then((chaves) =>
    Promise.all(chaves.filter((c) => c !== CACHE).map((c) => caches.delete(c)))));
  self.clients.claim();
});
self.addEventListener('fetch', (evento) => {
  const pedido = evento.request;
  if (pedido.method !== 'GET' || !pedido.url.includes('/aluno/')) return;
  evento.respondWith(
    fetch(pedido).then((resposta) => {
      const copia = resposta.clone();
      caches.open(CACHE).then((cache) => cache.put(pedido, copia));
      return resposta;
    }).catch(() => caches.match(pedido).then((guardada) => guardada || caches.match('/aluno/')))
  );
});
"""
    return HttpResponse(corpo, content_type="application/javascript")


def icone(request, tamanho: int = 192):
    """Icone simples em SVG->PNG nao disponivel aqui: devolve um SVG com a inicial da rede."""
    marca = marca_do_cliente(request)
    inicial = (marca["nome"] or "A")[0].upper()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}">'
        f'<rect width="{tamanho}" height="{tamanho}" rx="{tamanho // 5}" fill="{marca["cor"]}"/>'
        f'<text x="50%" y="58%" font-family="sans-serif" font-size="{tamanho // 2}" '
        f'fill="#ffffff" text-anchor="middle">{inicial}</text></svg>'
    )
    return HttpResponse(svg, content_type="image/svg+xml")


def offline(request):
    return render(request, "area_do_aluno/offline.html", {"marca": marca_do_cliente(request)})
