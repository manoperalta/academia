"""Demonstracao da fase 8: comissao, gamificacao, NPS, check-in e PWA (limpa o que cria)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from area_do_aluno.servicos import registrar_checkin
from core.models import Rede, Unidade
from financeiro.models import Pagamento, Plano
from gamificacao.models import Conquista, EventoDePontos, RegraDePontos, SaldoDePontos
from gamificacao.servicos import ranking, saldo_do_aluno
from nps.models import Pesquisa
from nps.servicos import nps, registrar_resposta
from professores.models import Professor
from remuneracao.models import ApuracaoDeComissao, RegraDeComissao, TipoDeComissao
from remuneracao.servicos import apurar_competencia, competencia, conferir_apuracao, marcar_paga
from usuarios.models import Usuario

SLUG = "demo-fase8-verificacao"
Rede.todos.filter(slug=SLUG).delete()
rede = Rede.todos.create(nome="Demo Fase 8", slug=SLUG, status="ativo")
unidade = Unidade.objects.create(rede=rede, nome="Centro", codigo="centro", status="ativa")
professor = Professor.todos.create(rede=rede, unidade=unidade, nome="Prof. Demo", status_prof="Ativo")
hoje = timezone.localdate()
plano = Plano.objects.create(rede=rede, unidade=unidade, nome="Mensal", tipo="mensal",
                             valor=Decimal("200.00"))
for posicao in range(2):
    login = get_user_model().objects.create_user(username="demo.f8.%d" % posicao, password="x")
    Usuario.todos.create(rede=rede, unidade=unidade, user=login, nome="Aluno Demo %d" % posicao,
                         status_user="Ativo")
    Pagamento.objects.create(rede=rede, unidade=unidade, usuario=login, plano=plano,
                             valor_pago=Decimal("200.00"), data_pagamento=hoje, data_inicio=hoje,
                             data_fim=hoje + timedelta(days=30), status="pago")

print("== 1) COMISSAO: regra de 10% do recebido + piso ==")
RegraDeComissao.objects.create(rede=rede, professor=professor, tipo=TipoDeComissao.PERCENTUAL,
                              percentual=Decimal("10.000"), piso_mensal=Decimal("100.00"))
inicio, fim = competencia()
resultado = apurar_competencia(rede, usuario=None)
print("   apuradas:", len(resultado["emitidas"]), "| total liquido: R$", resultado["total"],
      "| erros:", resultado["erros"])
apuracao = ApuracaoDeComissao.objects.get()
for item in apuracao.itens.all():
    print("   linha %d: %-38s base R$ %8s x %s%% = R$ %s" % (
        item.ordem, item.descricao[:38], item.base, item.percentual, item.valor))
conferencia = conferir_apuracao(apuracao)
print("   conferencia por recalculo:", "CONFERE" if conferencia["ok"] else "DIVERGE",
      "| mesmo numero:", conferencia["mesmo_numero"], "| hash:", apuracao.hash_do_calculo[:12])
marcar_paga(apuracao, apuracao.valor_devido)
apuracao.refresh_from_db()
print("   apos baixa: situacao =", apuracao.situacao, "| saldo = R$", apuracao.saldo)

print("== 2) GAMIFICACAO: check-in pontua, conquista e ranking ==")
RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.CHECKIN, pontos=10, limite_diario=1)
Conquista.objects.create(rede=rede, nome="Primeiro passo", evento=EventoDePontos.CHECKIN,
                         quantidade=1, pontos_bonus=5, icone="*")
aluno = Usuario.todos.filter(rede=rede).first()
checkin, ganho = registrar_checkin(aluno, unidade)
print("   check-in:", checkin.unidade.nome, "| pontos ganhos:", ganho.get("pontos"),
      "| conquistas:", [c["nome"] for c in ganho.get("conquistas", [])])
print("   saldo:", saldo_do_aluno(aluno)["pontos"], "pontos | nivel", saldo_do_aluno(aluno)["nivel"])
print("   ranking:", [(l["posicao"], l["nome"], l["pontos"]) for l in ranking(rede=rede)])

print("== 3) NPS: resposta pontua e detrator entra na fila ==")
RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.NPS, pontos=15)
pesquisa = Pesquisa.objects.create(rede=rede, titulo="Como foi o treino?", pergunta="Recomendaria?")
registrar_resposta(pesquisa, aluno=aluno, nota=10)
outro = Usuario.todos.filter(rede=rede).exclude(pk=aluno.pk).first()
registrar_resposta(pesquisa, aluno=outro, nota=4, comentario="chuveiro frio")
print("   resultado:", nps(pesquisa))
print("   alunos pontuando:", SaldoDePontos.objects.filter(rede=rede).count())

print("== 4) LIMPEZA ==")
Rede.todos.filter(slug=SLUG).delete()
print("   rede de demonstracao removida:", not Rede.todos.filter(slug=SLUG).exists())
