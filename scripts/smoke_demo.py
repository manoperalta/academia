"""Navega a demonstracao com cada perfil e reporta o status de cada tela.

Usa o cliente de teste do Django contra o banco do demo: se alguma tela quebrar (500), aparece aqui
antes de o usuario clicar.
"""

from __future__ import annotations

from django.test import Client

SENHA = "Demo@2026"

TELAS = {
    "dono@safestack.com.br": [
        ("/gestao/", "painel"),
        ("/plataforma/", "painel da plataforma"),
        ("/plataforma/tenants/", "redes"),
        ("/plataforma/auditoria/", "auditoria"),
        ("/plataforma/pacotes/", "pacotes"),
    ],
    "rede@demonstracao.com.br": [
        ("/gestao/", "painel"),
        ("/gestao/alunos/", "alunos"),
        ("/gestao/relatorios/", "relatorios"),
        ("/rede/painel/", "painel da rede"),
        ("/rede/comparativo/", "comparativo"),
        ("/gestao/comunicacao/", "comunicacao"),
        ("/conta/chamados/", "chamados"),
    ],
    "unidade@demonstracao.com.br": [
        ("/gestao/", "painel"),
        ("/gestao/alunos/", "alunos"),
        ("/gestao/professores/", "professores"),
        ("/gestao/planos/", "planos"),
        ("/gestao/agenda/", "agenda"),
        ("/financeiro/", "financeiro"),
        ("/cobranca/", "cobranca"),
        ("/cobranca/inadimplencia/", "inadimplencia"),
        ("/gestao/design/", "design system"),
    ],
    "professor@demonstracao.com.br": [
        ("/professor/", "agenda do professor"),
        ("/professor/alunos/", "meus alunos"),
        ("/professor/treinos/", "prescricao"),
        ("/professor/avaliacoes/", "avaliacoes"),
        ("/professor/comissoes/", "comissoes"),
    ],
    "aluno@demonstracao.com.br": [
        ("/aluno/", "home do aluno (PWA)"),
        ("/aluno/treinos/", "meus treinos"),
        ("/aluno/evolucao/", "minha evolucao"),
        ("/aluno/agenda/", "agenda"),
        ("/aluno/pagamentos/", "meus pagamentos"),
        ("/aluno/ficha/", "minha ficha"),
        ("/aluno/perfil/", "perfil"),
    ],
}

problemas = []
for email, caminhos in TELAS.items():
    print(f"\n== {email} ==")
    cliente = Client(HTTP_HOST="academia.safestack.com.br")
    entrou = cliente.login(username=email, password=SENHA)
    print(f"  login: {'OK' if entrou else 'FALHOU'}")
    if not entrou:
        problemas.append(f"{email}: nao entrou")
        continue
    for caminho, rotulo in caminhos:
        resposta = cliente.get(caminho)
        marca = "ok" if resposta.status_code < 400 else "PROBLEMA"
        if resposta.status_code >= 400:
            problemas.append(f"{email} {caminho} -> {resposta.status_code}")
        print(f"  {resposta.status_code}  {rotulo:26s} {caminho}   [{marca}]")

print()
if problemas:
    print("PROBLEMAS:")
    for item in problemas:
        print(" -", item)
else:
    print("TODAS AS TELAS ABRIRAM")
