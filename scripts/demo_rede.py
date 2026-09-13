"""Demonstracao da fase 6: 3 unidades na mesma rede + repasse emitido e conferido.

Roda no ambiente de dev, cria apenas o que precisa e no fim remove o que criou.
"""
from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Rede, Unidade
from financeiro.models import Pagamento, Plano
from rede.models import ItemDeChecklist, RegraDeRepasse, Repasse, TemplateDeUnidade
from rede.servicos import (
    comparativo_entre_unidades, conferir_repasse, emitir_repasses_do_mes, marcar_repasse_pago,
    periodo_do_mes, politica, travas_vigentes, validar_desconto,
)
from usuarios.models import Usuario

sufixo = secrets.token_hex(3)
print("=" * 78)
print("DEMONSTRACAO DA FASE 6 -- REDE COM 3 UNIDADES E REPASSE CONFERIDO")
print("=" * 78)

rede = Rede.todos.create(nome=f"Rede Demo {sufixo}", slug=f"rede-demo-{sufixo}", status="ativo")
unidades = [
    Unidade.objects.create(rede=rede, nome=f"Unidade {nome}", codigo=nome.lower(),
                           tipo=tipo, cidade=cidade, uf="RS", status="ativa")
    for nome, tipo, cidade in (("Centro", "propria", "Montenegro"),
                               ("ZonaSul", "franqueada", "Porto Alegre"),
                               ("Serra", "franqueada", "Gramado"))
]
print(f"\n1) REDE CRIADA: {rede.nome} ({rede.slug})")
for unidade in unidades:
    print(f"   • {unidade.nome:12s} {unidade.get_tipo_display():11s} {unidade.cidade}/{unidade.uf}")

hoje = timezone.localdate()
plano = Plano.objects.create(rede=rede, unidade=None, nome="Mensal", tipo="mensal",
                             valor=Decimal("180.00"))
for indice, unidade in enumerate(unidades):
    for posicao in range(2 + indice):
        login = get_user_model().objects.create_user(
            username=f"demo-{sufixo}-{indice}-{posicao}", password=secrets.token_urlsafe(12),
            email=f"{sufixo}-{indice}-{posicao}@exemplo.com")
        Usuario.todos.create(rede=rede, unidade=unidade, user=login,
                             nome=f"Aluno {indice}-{posicao}", status_user="Ativo")
        Pagamento.objects.create(rede=rede, unidade=unidade, usuario=login, plano=plano,
                                 valor_pago=Decimal("180.00"), data_pagamento=hoje,
                                 data_inicio=hoje, data_fim=hoje + timedelta(days=30), status="pago")
    login = get_user_model().objects.create_user(
        username=f"demo-pend-{sufixo}-{indice}", password=secrets.token_urlsafe(12),
        email=f"pend-{sufixo}-{indice}@exemplo.com")
    Pagamento.objects.create(rede=rede, unidade=unidade, usuario=login, plano=plano,
                             valor_pago=Decimal("180.00"), data_pagamento=hoje, data_inicio=hoje,
                             data_fim=hoje + timedelta(days=30), status="pendente")

regra = RegraDeRepasse.objects.create(
    rede=rede, unidade=None, tipo=RegraDeRepasse.Tipo.PERCENTUAL, percentual=Decimal("8.000"),
    base=RegraDeRepasse.Base.LIQUIDO, percentual_de_taxas_de_gateway=Decimal("2.50"),
    excluir_taxas_de_gateway=True, fundo_de_marketing=Decimal("1.50"), piso_minimo=Decimal("50.00"),
)
print(f"\n2) REGRA DA REDE: royalty {regra.percentual}% sobre {regra.get_base_display()}, "
      f"fundo {regra.fundo_de_marketing}%, taxas de gateway {regra.percentual_de_taxas_de_gateway}% "
      f"excluidas, piso R$ {regra.piso_minimo}")

inicio, fim = periodo_do_mes()
resultado = emitir_repasses_do_mes(rede, referencia=fim)
print(f"\n3) REPASSES EMITIDOS ({inicio:%d/%m} a {fim:%d/%m}): {len(resultado['emitidos'])} unidade(s), "
      f"total R$ {resultado['total']}")
for item in resultado["emitidos"]:
    print(f"   • {item['unidade']:12s} R$ {item['valor']}")

primeiro = Repasse.objects.filter(rede=rede).order_by("-valor_devido").first()
print(f"\n4) DEMONSTRATIVO DE {primeiro.unidade.nome.upper()} (memoria de calculo)")
for item in primeiro.itens.all():
    print(f"   {item.ordem}. [{item.get_tipo_display():22s}] {item.descricao[:52]:52s} "
          f"base R$ {item.base:>8} × {item.percentual:>6}% = R$ {item.valor:>8}")
print(f"   TOTAL DEVIDO: R$ {primeiro.valor_devido}  (hash {primeiro.hash_do_calculo[:16]}…)")

conferencia = conferir_repasse(primeiro)
print(f"\n5) CONFERENCIA LINHA A LINHA: {'OK' if conferencia['ok'] else 'DIVERGENCIA'} "
      f"(mesmo numero no recalculo: {conferencia['mesmo_numero']}, "
      f"{len(conferencia['divergencias'])} divergencia(s))")

comparativo = comparativo_entre_unidades(rede, inicio, fim)
print("\n6) COMPARATIVO ENTRE UNIDADES")
for linha in comparativo:
    print(f"   {linha['posicao']}o {linha['unidade'].nome:12s} recebido R$ {linha['recebido']:>8} · "
          f"{linha['alunos_ativos']} aluno(s) · ticket R$ {linha['ticket_medio']:>7} · "
          f"inadimplencia {linha['inadimplencia']}% · repasse R$ {linha['repasse']:>7}")

print("\n7) GOVERNANCA E ALCADAS")
travas = travas_vigentes(rede)
for campo, travado in travas.items():
    print(f"   {'TRAVADO' if travado else 'livre  '} {campo}")
dentro = validar_desconto(unidades[0], Decimal("5.00"))
fora = validar_desconto(unidades[0], Decimal("30.00"))
print(f"   desconto 5% -> permitido={dentro['permitido']} · desconto 30% -> "
      f"permitido={fora['permitido']} (exige aprovacao={fora['exige_aprovacao']})")

modelo = TemplateDeUnidade.objects.create(
    rede=rede, nome="Padrao franquia",
    configuracoes={"planos": ["Mensal"], "grades": ["manha"], "mensagens": ["boas-vindas"],
                   "branding": {"sobrescrever": False}})
ItemDeChecklist.objects.create(template=modelo, titulo="Cadastrar CNPJ", ordem=1)
ItemDeChecklist.objects.create(template=modelo, titulo="Treinar equipe", ordem=2)
print(f"\n8) ONBOARDING: template {modelo.nome!r} com {modelo.itens.count()} passo(s) de checklist")

marcar_repasse_pago(primeiro, primeiro.valor_devido)
primeiro.refresh_from_db()
print(f"\n9) BAIXA REGISTRADA: situacao {primeiro.get_situacao_display()}, "
      f"saldo R$ {primeiro.saldo}")

# limpeza do que a demonstracao criou
Repasse.objects.filter(rede=rede).delete()
Pagamento.objects.filter(rede=rede).delete()
Usuario.todos.filter(rede=rede).delete()
Unidade.objects.filter(rede=rede).delete()
RegraDeRepasse.objects.filter(rede=rede).delete()
TemplateDeUnidade.objects.filter(rede=rede).delete()
Plano.objects.filter(rede=rede).delete()
get_user_model().objects.filter(username__startswith=f"demo-{sufixo}").delete()
get_user_model().objects.filter(username__startswith=f"demo-pend-{sufixo}").delete()
rede.delete()
print("\n10) LIMPEZA: rede de demonstracao removida (nada seu foi tocado)")
print("=" * 78)
print("FIM DA DEMONSTRACAO DA FASE 6")
print("=" * 78)
