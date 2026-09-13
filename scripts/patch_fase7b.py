#!/usr/bin/env python3
"""Fase 7b: preserva /api/v1/estado/ (fase 1) e move o estado da rede para /estado-da-rede/."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def patch_urls() -> None:
    caminho = RAIZ / "api" / "urls.py"
    texto = caminho.read_text(encoding="utf-8")
    if "estado-da-rede" in texto:
        print("api/urls.py: ja ajustado")
        return
    texto = texto.replace(
        '    path("v1/estado/", ep.EstadoDoTenant.as_view(), name="api-estado"),',
        '    path("v1/estado/", EstadoDaInstalacao.as_view(), name="api-estado"),\n'
        '    path("v1/estado-da-rede/", ep.EstadoDoTenant.as_view(), name="api-estado-rede"),',
        1,
    )
    if not texto.count("EstadoDaInstalacao"):
        raise SystemExit("ERRO: EstadoDaInstalacao nao voltou para /v1/estado/")
    if "from api.views import" not in texto:
        texto = texto.replace("from api import endpoints as ep",
                              "from api import endpoints as ep\nfrom api.views import EstadoDaInstalacao", 1)
    if "EstadoDaInstalacao" not in texto.split("urlpatterns")[0]:
        raise SystemExit("ERRO: import de EstadoDaInstalacao ausente")
    caminho.write_text(texto, encoding="utf-8")
    print("api/urls.py: /v1/estado/ (fase 1) preservado e /v1/estado-da-rede/ criado")


def patch_apoio() -> None:
    caminho = RAIZ / "tests" / "apoio.py"
    texto = caminho.read_text(encoding="utf-8")
    if "api.tarefaassincrona" in texto:
        print("apoio: modelos da API ja ignorados")
        return
    alvo = 'ignorados = {"accounts.customuser", "api.apitoken", "api.registroauditoria"}'
    if alvo not in texto:
        raise SystemExit("ERRO: conjunto ignorados nao encontrado")
    texto = texto.replace(
        alvo,
        'ignorados = {"accounts.customuser", "api.apitoken", "api.registroauditoria",\n'
        '                  "api.webhookdesaida", "api.entregadewebhook", "api.tarefaassincrona"}',
        1,
    )
    if "api.tarefaassincrona" not in texto:
        raise SystemExit("ERRO: modelos da API nao entraram")
    caminho.write_text(texto, encoding="utf-8")
    print("apoio: webhooks/tarefas da API marcados como entidades de plataforma")


if __name__ == "__main__":
    patch_urls()
    patch_apoio()
    print("patch fase 7b concluido")
