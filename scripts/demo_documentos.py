"""Gera os documentos de negocio com dados reais de uma rede de demonstracao (limpa depois)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade
from documentos import servicos
from financeiro.models import Pagamento, Plano
from professores.models import Professor
from remuneracao.models import RegraDeComissao, TipoDeComissao
from remuneracao.servicos import apurar_competencia
from usuarios.models import Usuario

SLUG = "demo-documentos-verificacao"
Rede.todos.filter(slug=SLUG).delete()
rede = Rede.todos.create(nome="Academia Peralta", slug=SLUG, cnpj="12.345.678/0001-90")
unidade = Unidade.objects.create(
    rede=rede,
    nome="Unidade Centro",
    codigo="centro",
    tipo="propria",
    endereco="Rua das Acacias, 100",
    cidade="Montenegro",
    uf="RS",
    telefone="51 3632-0000",
)
professor = Professor.todos.create(
    rede=rede, unidade=unidade, nome="Prof. Joao", status_prof="Ativo"
)
login = get_user_model().objects.create_user(username="aluno.demo.doc", password="SenhaDemo!23")
aluno = Usuario.todos.create(
    rede=rede, unidade=unidade, user=login, nome="Joao Conceicao da Silva", status_user="Ativo"
)
plano = Plano.objects.create(
    rede=rede, unidade=unidade, nome="Mensal Ouro", tipo="mensal", valor=Decimal("199.00")
)
hoje = timezone.localdate()
pagamento = Pagamento.objects.create(
    rede=rede,
    unidade=unidade,
    usuario=login,
    plano=plano,
    valor_pago=Decimal("189.05"),
    data_pagamento=hoje,
    data_inicio=hoje,
    data_fim=hoje + timedelta(days=30),
    status="pago",
)
RegraDeComissao.objects.create(
    rede=rede,
    professor=professor,
    tipo=TipoDeComissao.PERCENTUAL,
    percentual=Decimal("10.000"),
    piso_mensal=Decimal("50.00"),
)
apurar_competencia(rede)
from remuneracao.models import ApuracaoDeComissao  # noqa: E402 - import depois do setup do Django

apuracao = ApuracaoDeComissao.objects.get()

documentos = {
    "comprovante-de-matricula": servicos.comprovante_de_matricula(login),
    "carteirinha": servicos.carteirinha_do_aluno(login),
    "contrato-de-adesao": servicos.contrato_de_adesao(login, plano),
    "recibo-de-pagamento": servicos.recibo_de_pagamento(pagamento),
    "extrato-de-comissao": servicos.extrato_de_comissao(apuracao),
}
for nome, conteudo in documentos.items():
    assert conteudo.startswith(b"%PDF-1.4"), f"{nome} nao e PDF"
    assert b"/Type /Catalog" in conteudo and b"startxref" in conteudo, f"{nome} incompleto"
    paginas = conteudo.count(b"/Type /Page ")
    print(f"   {nome:26s} {len(conteudo):6d} bytes | paginas: {paginas}")
extrato = documentos["extrato-de-comissao"].decode("latin-1")
print("   extrato traz a memoria:", "Percentual do recebido na unidade" in extrato)
print("   extrato traz o hash:", apuracao.hash_do_calculo[:16] in extrato)
carteirinha = documentos["carteirinha"].decode("latin-1")
print("   acento preservado na carteirinha:", "Concei\u00e7\u00e3o" in carteirinha)
Rede.todos.filter(slug=SLUG).delete()
print("   rede de demonstracao removida:", not Rede.todos.filter(slug=SLUG).exists())
