"""Diagnostico do score de risco, mostrando cada sinal (nao altera nada de producao)."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from area_do_aluno.models import CheckinDoAluno
from core.models import Rede, Unidade
from financeiro.models import Pagamento, Plano
from nps.models import Pesquisa, Resposta, TipoDePesquisa
from relacionamento import servicos
from usuarios.models import Usuario

SLUG = "diag-risco"
Rede.todos.filter(slug=SLUG).delete()
rede = Rede.todos.create(nome="Diag", slug=SLUG, status="ativo")
unidade = Unidade.objects.create(rede=rede, nome="Centro", codigo="centro", tipo="propria")
login = get_user_model().objects.create_user(username="diag.risco", password="SenhaDiag!23")
aluno = Usuario.todos.create(rede=rede, unidade=unidade, user=login, nome="Aluno Diagnostico",
                             status_user="Ativo")
plano = Plano.objects.create(rede=rede, unidade=unidade, nome="Mensal", tipo="mensal",
                             valor=Decimal("199.00"))
hoje = timezone.localdate()
p = Pagamento.objects.create(rede=rede, unidade=unidade, usuario=login, plano=plano,
                             valor_pago=Decimal("199.00"), data_inicio=hoje - timedelta(days=70),
                             data_fim=hoje - timedelta(days=40), status="pago")
entrada = CheckinDoAluno.objects.create(rede=rede, aluno=aluno, unidade=unidade)
CheckinDoAluno.objects.filter(pk=entrada.pk).update(criado_em=timezone.now() - timedelta(days=45))
pesquisa = Pesquisa.objects.create(rede=rede, unidade=unidade, titulo="Pos-aula",
                                   pergunta="De 0 a 10?", tipo=TipoDePesquisa.NPS)
Resposta.objects.create(pesquisa=pesquisa, aluno=aluno, unidade=unidade, nota=3)

print("data_fim do pagamento:", p.data_fim, "| hoje:", hoje, "| status:", p.status)
print("checkins do aluno:", CheckinDoAluno.objects.filter(aluno=aluno).count())
ultimo = CheckinDoAluno.objects.filter(aluno=aluno).order_by("-criado_em").first()
print("ultimo checkin:", ultimo.criado_em if ultimo else None)
print("respostas de detrator:", Resposta.objects.filter(aluno=aluno, nota__lte=6).count())
print("tem criado_em no perfil?:", hasattr(aluno, "criado_em"))
conta = servicos.calcular_risco(aluno)
print("PONTUACAO:", conta["pontuacao"], "| faixa:", conta["faixa"])
for motivo in conta["motivos"]:
    print("   -", motivo)
Rede.todos.filter(slug=SLUG).delete()
