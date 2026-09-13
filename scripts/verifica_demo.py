"""Confere os numeros da demonstracao e testa os 5 logins."""

from __future__ import annotations

from django.contrib.auth import authenticate

from agendamento.models import Agendamento
from cobranca.models import CobrancaRecorrente
from core.models import Rede, Unidade, VinculoUsuario
from financeiro.models import Pagamento
from treinos.models import AvaliacaoFisica, ExercicioDoTreino, Treino
from usuarios.models import Usuario

print("REDE..........:", Rede.todos.filter(slug="demonstracao").count())
print("UNIDADES......:", Unidade.objects.count())
print("ALUNOS........:", Usuario.todos.count())
print("PAGAMENTOS....:", Pagamento.objects.count())
print("  em atraso...:", Pagamento.objects.exclude(status="pago").count())
print("AGENDAMENTOS..:", Agendamento.objects.count())
print("COBRANCAS.....:", CobrancaRecorrente.objects.count())
print("VINCULOS......:", VinculoUsuario.todos.count())
print("TREINOS.......:", Treino.objects.count(), "| exercicios:", ExercicioDoTreino.objects.count(),
      "| avaliacoes:", AvaliacaoFisica.objects.count())

for email in [
    "dono@safestack.com.br",
    "rede@demonstracao.com.br",
    "unidade@demonstracao.com.br",
    "professor@demonstracao.com.br",
    "aluno@demonstracao.com.br",
]:
    usuario = authenticate(username=email, password="Demo@2026")
    print(f"LOGIN {email:34s} -> {'OK' if usuario else 'FALHOU'}")
