"""Navega a demonstracao resolvendo as rotas POR NOME (como o menu faz) e reporta cada tela."""

from __future__ import annotations

from django.conf import settings
from django.test import Client
from django.urls import NoReverseMatch, reverse

SENHA = "Demo@2026"

PERFIS = {
    "dono@safestack.com.br": [
        "gestao:visao_geral", "plataforma:metricas", "plataforma:tenants", "plataforma:pacotes",
        "plataforma:faturas", "plataforma:regua", "plataforma:auditoria",
    ],
    "rede@demonstracao.com.br": [
        "gestao:visao_geral", "gestao:alunos", "gestao:professores", "gestao:relatorios",
        "gestao:comunicacao", "gestao:auditoria", "gestao:privacidade",
        "rede:painel", "rede:unidades", "rede:comparativo", "rede:metas", "rede:repasses",
        "rede:governanca", "rede:catalogo", "rede:comunicados",
        "conta:perfil", "conta:sessoes", "conta:chamados",
    ],
    "unidade@demonstracao.com.br": [
        "gestao:visao_geral", "gestao:alunos", "gestao:professores", "gestao:aulas",
        "gestao:agenda", "gestao:relatorios", "gestao:comunicacao", "gestao:equipe",
        "gestao:design", "cobranca:painel", "cobranca:inadimplencia", "cobranca:autorizacoes",
        "acesso:painel", "pdv:balcao", "fiscal:painel", "relacionamento:funil", "busca:busca",
        "midia:lista", "documentos:envelopes",
    ],
    "professor@demonstracao.com.br": [
        "professor:agenda", "professor:alunos", "professor:treinos", "professor:avaliacoes",
        "professor:comissoes",
    ],
    "aluno@demonstracao.com.br": [
        "aluno:inicio", "treinos:meus_treinos", "treinos:minha_evolucao", "portal:agenda",
        "portal:pagamentos", "portal:ficha", "portal:perfil", "aluno:pontos",
    ],
}

problemas = []
faltando = set()
for email, nomes in PERFIS.items():
    print(f"\n== {email} ==")
    cliente = Client(HTTP_HOST="academia.safestack.com.br")
    if not cliente.login(username=email, password=SENHA):
        problemas.append(f"{email}: nao entrou")
        print("  login FALHOU")
        continue
    for nome in nomes:
        try:
            caminho = reverse(nome)
        except NoReverseMatch:
            faltando.add(nome)
            continue
        # no cliente de teste nao existe uWSGI para tirar o prefixo: o pedido vai sem ele
        efetivo = caminho[len(settings.FORCE_SCRIPT_NAME):] if settings.FORCE_SCRIPT_NAME else caminho
        resposta = cliente.get(efetivo or "/")
        if resposta.status_code >= 400:
            problemas.append(f"{email} {nome} ({caminho}) -> {resposta.status_code}")
        marca = "ok" if resposta.status_code < 400 else "PROBLEMA"
        print(f"  {resposta.status_code}  {nome:28s} {caminho:34s} [{marca}]")

print()
if faltando:
    print("rotas que nao existem com esse nome:", ", ".join(sorted(faltando)))
print()
if problemas:
    print("PROBLEMAS:")
    for item in problemas:
        print(" -", item)
else:
    print("TODAS AS TELAS ABRIRAM")
