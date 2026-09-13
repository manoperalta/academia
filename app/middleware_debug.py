"""Mantem o modo de depuracao do laboratorio sem vazar dados para o publico.

Com DEBUG=True o Django imprime SECRET_KEY, variaveis de ambiente e todas as
settings na pagina de erro 500 (e lista as rotas da aplicacao no 404). Isso e
util enquanto se desenvolve e inaceitavel num host publico.

Este middleware libera as paginas de debug apenas para quem traz o token de
`DJANGO_DEBUG_TOKEN` (ver .env), uma vez na URL:

    https://<host>/?debug=<token>     -> grava cookie e libera o debug

Do cookie em diante aquele navegador continua autorizado; o resto do mundo ve
404/500 limpos e o traceback completo fica no log do container
(`docker logs academia_web`).

Como o debug e barrado -- tres caminhos, porque o Django trata cada caso num
lugar diferente:

  1. excecao na view (500/404)  -> hook `process_exception` (o handler consulta
     os middlewares antes de montar a pagina tecnica);
  2. 404 de URL inexistente     -> o `Resolver404` e convertido em pagina de
     debug ANTES de subir para o middleware, entao a resposta e saneada no
     `__call__` (marcadores abaixo);
  3. qualquer resto             -> try/except no `__call__`.

Com DEBUG=False o middleware e um no-op: o Django trata 404/500 normalmente.

Efeito colateral conhecido: a excecao nao sobe ate o handler, entao o sinal
`got_request_exception` nao dispara em requisicao publica; o erro continua
registrado pelo logger deste modulo.
"""

import hmac
import logging

from django.conf import settings
from django.http import Http404, HttpResponseNotFound, HttpResponseServerError

logger = logging.getLogger(__name__)

COOKIE = "debug_token"
PARAM = "debug"
UM_ANO = 60 * 60 * 24 * 365

# Marcadores que so aparecem nas paginas tecnicas do Django (nao traduzidas).
MARCADORES_DEBUG = (
    b"DEBUG = True",
    b"Page not found at",
    b"technical_404",
    b"Traceback (most recent call last)",
)

_ESTILO = (
    "body{background:#0f1115;color:#e6e6e6;margin:0;display:flex;min-height:100vh;"
    "align-items:center;justify-content:center;text-align:center;"
    "font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}"
    "div{max-width:34rem;padding:2rem}h1{font-size:3.5rem;margin:0 0 .5rem}"
    "p{color:#9aa0a6;line-height:1.6;margin:.4rem 0}"
    "a{color:#4da3ff;text-decoration:none}"
)

PAGINA_404 = (
    '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>404 - Pagina nao encontrada</title><style>" + _ESTILO + "</style></head>"
    "<body><div><h1>404</h1><p>Esta pagina nao existe.</p>"
    '<p><a href="/">Voltar para a pagina inicial</a></p></div></body></html>'
)

PAGINA_500 = (
    '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    "<title>500 - Erro no servidor</title><style>" + _ESTILO + "</style></head>"
    "<body><div><h1>500</h1><p>Algo deu errado do nosso lado. O erro foi registrado.</p>"
    '<p><a href="/">Voltar para a pagina inicial</a></p></div></body></html>'
)


class DebugLocalAutorizadoMiddleware:
    """Libera as paginas de debug so para quem traz o token; limpa para o resto."""

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _token():
        return getattr(settings, "DEBUG_TOKEN", "") or ""

    @staticmethod
    def _confere(valor, token):
        return bool(valor) and bool(token) and hmac.compare_digest(str(valor), str(token))

    def _esta_autorizado(self, request):
        token = self._token()
        if self._confere(request.GET.get(PARAM), token):
            request._debug_via_token = True
            return True
        return self._confere(request.COOKIES.get(COOKIE), token)

    @staticmethod
    def _corpo(resposta):
        """Conteudo da resposta; renderiza TemplateResponse se ainda nao renderizou."""
        try:
            if hasattr(resposta, "render") and not getattr(resposta, "is_rendered", True):
                resposta = resposta.render()
            return bytes(resposta.content)
        except Exception:
            return b""

    def _limpar(self, resposta):
        """Troca a pagina tecnica do Django (resolver 404/500) por uma pagina limpa."""
        if resposta.status_code not in (404, 500) or "text/html" not in resposta.get(
            "Content-Type", ""
        ):
            return resposta
        corpo = self._corpo(resposta)
        if not any(marcador in corpo for marcador in MARCADORES_DEBUG):
            return resposta
        nova = PAGINA_404 if resposta.status_code == 404 else PAGINA_500
        logger.info(
            "Pagina de debug do Django barrada (HTTP %s) para requisicao sem token",
            resposta.status_code,
        )
        if resposta.status_code == 404:
            return HttpResponseNotFound(nova)
        return HttpResponseServerError(nova)

    def __call__(self, request):
        token = self._token()
        if not settings.DEBUG or not token:
            return self.get_response(request)

        if self._esta_autorizado(request):
            request._debug_autorizado = True
            resposta = self.get_response(request)
            if getattr(request, "_debug_via_token", False):
                resposta.set_cookie(
                    COOKIE,
                    token,
                    max_age=UM_ANO,
                    httponly=True,
                    samesite="Lax",
                    secure=request.is_secure(),
                )
            return resposta

        request._debug_autorizado = False
        try:
            resposta = self.get_response(request)
        except Http404:
            return HttpResponseNotFound(PAGINA_404)
        except Exception as exc:
            logger.exception(
                "Erro nao tratado em requisicao sem token de depuracao (%s)",
                type(exc).__name__,
            )
            return HttpResponseServerError(PAGINA_500)
        return self._limpar(resposta)

    def process_exception(self, request, exception):
        """Primeira linha para excecoes levantadas dentro da view."""
        if not settings.DEBUG or not self._token():
            return None
        if getattr(request, "_debug_autorizado", False):
            return None
        if isinstance(exception, Http404):
            return HttpResponseNotFound(PAGINA_404)
        logger.exception("Erro nao tratado (via handler) sem token de depuracao")
        return HttpResponseServerError(PAGINA_500)
