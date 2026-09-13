"""Reproduz o caminho da view de agendar e mostra onde falha."""

from __future__ import annotations

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from agendamento.models import Agendamento
from core.models import Rede, Unidade
from painel.models import Painel
from portal_do_aluno import servicos
from usuarios.models import Usuario

rede = Rede.todos.filter(slug="diag-agendar").first() or Rede.todos.create(
    nome="Diag", slug="diag-agendar", status="ativo"
)
unidade = Unidade.objects.filter(rede=rede).first() or Unidade.objects.create(
    rede=rede, nome="Centro", codigo="centro", tipo="propria"
)
login, _ = get_user_model().objects.get_or_create(username="diag.aluno")
login.set_password("SenhaDiag!23")
login.save()
aluno, _criado = Usuario.todos.get_or_create(
    rede=rede,
    user=login,
    defaults={"unidade": unidade, "nome": "Aluno Diag", "status_user": "Ativo"},
)
dono, _ = get_user_model().objects.get_or_create(username="diag.dono")
turma, _criada = Painel.objects.get_or_create(
    rede=rede,
    nome="Turma Diag",
    defaults={
        "unidade": unidade,
        "data": timezone.localdate() + timedelta(days=2),
        "hora_inicio": time(19, 0),
        "hora_fim": time(20, 0),
        "numero_de_user": 2,
        "responsavel": dono,
    },
)
print("rede do aluno:", aluno.rede_id, "| rede da turma:", turma.rede_id)
print("arquivado:", turma.arquivado_em, "| data:", turma.data, "| hoje:", timezone.localdate())
print("capacidade:", turma.numero_de_user)
existentes = Agendamento.objects.filter(aluno=aluno.user, painel=turma).count()
print("agendamentos existentes:", existentes)
try:
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    print("OK criado:", agendamento.pk, agendamento.status)
except Exception as erro:
    print("FALHOU:", type(erro).__name__, "-", erro)
Agendamento.objects.filter(aluno=aluno.user).delete()
Painel.objects.filter(nome="Turma Diag").delete()
Rede.todos.filter(slug="diag-agendar").delete()
