"""Views de governanca: login seguro, 2FA, midia protegida, status e privacidade."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from core.seguranca import (
    acesso_a_midia_permitido,
    bloqueio_ativo,
    confirmar_2fa,
    desativar_2fa,
    dispositivo_do,
    dois_fatores_ativo,
    exigir_2fa_para,
    gerar_codigos_de_recuperacao,
    iniciar_2fa,
    limpar_falhas_de_login,
    marcar_sessao_verificada,
    registrar_falha_de_login,
    validar_segundo_fator,
)
from governanca.forms import Codigo2FAForm, Desativar2FAForm, LoginSeguroForm
from governanca.models import RegistroBackup, TentativaDeLogin
from governanca.servicos import alertas_pendentes, resumo_de_saude
from plataforma.models import ConfiguracaoPlataforma

logger = logging.getLogger("governanca")


class LoginSeguroView(View):
    """Login com rate limit, bloqueio progressivo, registro e 2FA quando ativo."""

    template_name = "governanca/entrar.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(request.GET.get("proximo") or reverse("gestao:visao_geral"))
        return render(request, self.template_name, {"form": LoginSeguroForm()})

    def post(self, request):
        formulario = LoginSeguroForm(request.POST)
        proximo = request.POST.get("proximo") or request.GET.get("proximo") or ""
        if not formulario.is_valid():
            return render(request, self.template_name, {"form": formulario, "proximo": proximo})

        identificador = formulario.cleaned_data["identificador"].strip().lower()
        ip = _ip_do_cliente(request)
        bloqueado, espera, tentativas = bloqueio_ativo(identificador, ip)
        if bloqueado:
            TentativaDeLogin.objects.create(identificador=identificador, ip=ip, bloqueado=True)
            minutos = max(1, espera // 60)
            return render(
                request,
                self.template_name,
                {
                    "form": formulario,
                    "bloqueado_ate": minutos,
                    "tentativas": tentativas,
                    "erro": f"Muitas tentativas. Tente novamente em {minutos} minuto(s).",
                },
            )

        usuario = authenticate(
            request,
            username=_usuario_por_identificador(identificador) or identificador,
            password=formulario.cleaned_data["senha"],
        )
        if usuario is None:
            registrar_falha_de_login(identificador, ip)
            TentativaDeLogin.objects.create(identificador=identificador, ip=ip, sucesso=False)
            return render(
                request,
                self.template_name,
                {
                    "form": formulario,
                    "erro": "E-mail ou senha incorretos.",
                    "proximo": proximo,
                },
            )

        limpar_falhas_de_login(identificador, ip)
        TentativaDeLogin.objects.create(identificador=identificador, ip=ip, sucesso=True)
        login(request, usuario)
        from api.auditoria import registrar

        registrar(
            "login",
            "usuario",
            entidade_id=usuario.pk,
            descricao=f"Acesso pelo e-mail {identificador}",
            request=request,
        )
        if dois_fatores_ativo(usuario):
            return redirect(f"{reverse('governanca:dois_fatores')}?proximo={proximo}")
        if exigir_2fa_para(usuario):
            return redirect(f"{reverse('governanca:dois_fatores_cadastrar')}?obrigatorio=1")
        return redirect(proximo or reverse("gestao:visao_geral"))


def _usuario_por_identificador(identificador: str):
    from django.contrib.auth import get_user_model

    usuario = get_user_model().objects.filter(email__iexact=identificador).first()
    return usuario.username if usuario else None


def _ip_do_cliente(request) -> str:
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class DoisFatoresView(View):
    """Desafio do segundo fator."""

    template_name = "governanca/dois_fatores.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("governanca:entrar")
        if not dois_fatores_ativo(request.user):
            return redirect("governanca:dois_fatores_cadastrar")
        return render(
            request,
            self.template_name,
            {
                "form": Codigo2FAForm(),
                "proximo": request.GET.get("proximo", ""),
            },
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("governanca:entrar")
        formulario = Codigo2FAForm(request.POST)
        proximo = request.POST.get("proximo", "")
        if formulario.is_valid() and validar_segundo_fator(
            request.user, formulario.cleaned_data["codigo"]
        ):
            marcar_sessao_verificada(request)
            from api.auditoria import registrar

            registrar(
                "2fa",
                "usuario",
                entidade_id=request.user.pk,
                descricao="Segundo fator aceito",
                request=request,
            )
            return redirect(proximo or reverse("gestao:visao_geral"))
        TentativaDeLogin.objects.create(
            identificador=f"2fa:{request.user.username}",
            ip=_ip_do_cliente(request),
            sucesso=False,
            bloqueado=True,
        )
        return render(
            request,
            self.template_name,
            {
                "form": formulario,
                "proximo": proximo,
                "erro": "Codigo invalido. Confira o app autenticador (ou use um codigo de recuperacao).",
            },
        )


class Cadastrar2FAView(LoginRequiredMixin, View):
    """Ativacao do 2FA: mostra o segredo, confirma com um codigo e entrega os codigos de recuperacao."""

    template_name = "governanca/2fa_cadastrar.html"

    def get(self, request):
        dispositivo = dispositivo_do(request.user)
        if dispositivo is None or not dispositivo.confirmado_em:
            dispositivo = iniciar_2fa(request.user)
        from core import totp

        return render(
            request,
            self.template_name,
            {
                "segredo": dispositivo.segredo,
                "uri": totp.uri_otpauth(
                    dispositivo.segredo, request.user.email or request.user.username
                ),
                "form": Codigo2FAForm(),
                "obrigatorio": request.GET.get("obrigatorio") == "1"
                or exigir_2fa_para(request.user),
                "ativo": bool(dispositivo.confirmado_em),
            },
        )

    def post(self, request):
        formulario = Codigo2FAForm(request.POST)
        if formulario.is_valid() and confirmar_2fa(request.user, formulario.cleaned_data["codigo"]):
            codigos = gerar_codigos_de_recuperacao(request.user)
            marcar_sessao_verificada(request)
            from api.auditoria import registrar

            registrar(
                "2fa",
                "usuario",
                entidade_id=request.user.pk,
                descricao="2FA ativado",
                request=request,
            )
            return render(
                request, "governanca/2fa_codigos.html", {"codigos": codigos, "novos": True}
            )
        from core import totp

        dispositivo = iniciar_2fa(request.user)
        return render(
            request,
            self.template_name,
            {
                "segredo": dispositivo.segredo,
                "uri": totp.uri_otpauth(
                    dispositivo.segredo, request.user.email or request.user.username
                ),
                "form": formulario,
                "erro": "Codigo incorreto. Confira o horario do celular e tente de novo.",
                "obrigatorio": request.GET.get("obrigatorio") == "1"
                or exigir_2fa_para(request.user),
                "ativo": False,
            },
        )


class CodigosDeRecuperacaoView(LoginRequiredMixin, View):
    template_name = "governanca/2fa_codigos.html"

    def post(self, request):
        codigos = gerar_codigos_de_recuperacao(request.user)
        messages.success(request, "Novos codigos gerados. Os anteriores deixaram de valer.")
        return render(request, self.template_name, {"codigos": codigos, "novos": True})


class Desativar2FAView(LoginRequiredMixin, View):
    template_name = "governanca/2fa_desativar.html"

    def get(self, request):
        if exigir_2fa_para(request.user):
            messages.error(request, "O segundo fator e obrigatorio para a equipe da plataforma.")
            return redirect("gestao:seguranca")
        return render(request, self.template_name, {"form": Desativar2FAForm()})

    def post(self, request):
        if exigir_2fa_para(request.user):
            messages.error(request, "O segundo fator e obrigatorio para a equipe da plataforma.")
            return redirect("gestao:seguranca")
        formulario = Desativar2FAForm(request.POST)
        if formulario.is_valid():
            if not request.user.check_password(formulario.cleaned_data["senha"]):
                formulario.add_error("senha", "Senha incorreta.")
            elif not validar_segundo_fator(request.user, formulario.cleaned_data["codigo"]):
                formulario.add_error("codigo", "Codigo incorreto.")
            else:
                desativar_2fa(request.user)
                from api.auditoria import registrar

                registrar(
                    "2fa",
                    "usuario",
                    entidade_id=request.user.pk,
                    descricao="2FA desativado",
                    request=request,
                )
                messages.success(request, "Segundo fator desativado.")
                return redirect("gestao:seguranca")
        return render(request, self.template_name, {"form": formulario})


class SairView(LoginRequiredMixin, View):
    def post(self, request):
        logout(request)
        return redirect("vitrine:home")


class MidiaView(View):
    """Servidor de midia com acesso controlado por cliente (RNF-010).

    O arquivo so e entregue para quem tem vinculo com o cliente dono do namespace.
    Atras do nginx, usa X-Accel-Redirect (nao passa o arquivo pelo Python).
    """

    def get(self, request, caminho: str):

        if not request.user.is_authenticated:
            return HttpResponseRedirect(f"{reverse('governanca:entrar')}?proximo={request.path}")
        if not acesso_a_midia_permitido(request.user, caminho):
            logger.warning("midia negada para %s: %s", request.user, caminho)
            raise Http404("Arquivo nao encontrado.")

        raiz = Path(settings.MEDIA_ROOT).resolve()
        destino = (raiz / caminho).resolve()
        if not str(destino).startswith(str(raiz)) or not destino.is_file():
            raise Http404("Arquivo nao encontrado.")

        interno = f"{settings.MEDIA_URL.rstrip('/')}/{caminho}"
        if getattr(settings, "USAR_X_ACCEL", False):
            resposta = HttpResponseRedirect("")
            resposta["X-Accel-Redirect"] = interno
            return resposta
        tipo, _ = mimetypes.guess_type(destino.name)
        return FileResponse(destino.open("rb"), content_type=tipo or "application/octet-stream")


class StatusView(TemplateView):
    """Pagina de status simples, sem dado sensivel (RNF-008)."""

    template_name = "governanca/status.html"

    def get_context_data(self, **kwargs):
        from django.db import connection

        contexto = super().get_context_data(**kwargs)
        banco_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as erro:
            banco_ok = False
            contexto["erro_banco"] = str(erro)[:200]
        ultimo_backup = (
            RegistroBackup.objects.filter(tipo=RegistroBackup.Tipo.BANCO)
            .order_by("-criado_em")
            .first()
        )
        saude = resumo_de_saude(horas=24)
        contexto.update(
            banco_ok=banco_ok,
            ultimo_backup=ultimo_backup,
            saude=saude,
            alertas=alertas_pendentes(),
            agora=timezone.now(),
            versao=getattr(settings, "VERSAO", "1.0"),
            clientes=saude["linhas"],
        )
        return contexto


class PrivacidadeView(TemplateView):
    """Politica de privacidade e bases legais (LGPD/RNF-006)."""

    template_name = "governanca/privacidade.html"

    def get_context_data(self, **kwargs):
        from governanca.models import RegraRetencao

        contexto = super().get_context_data(**kwargs)
        contexto["regras"] = RegraRetencao.objects.filter(ativo=True)
        contexto["configuracao"] = ConfiguracaoPlataforma.obter()
        contexto["controlador"] = "a academia contratante"
        contexto["operadora"] = ConfiguracaoPlataforma.obter().nome_emitente
        return contexto
