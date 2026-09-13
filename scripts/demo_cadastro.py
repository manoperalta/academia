"""Demonstracao ponta a ponta do cadastro self-service (ambiente de dev).

Roda com:  python manage.py shell < scripts/demo_cadastro.py

Mostra o fluxo do PRD 11.1: site -> planos -> cadastro -> provisionamento ->
e-mail/link de primeiro acesso -> senha -> painel operando, incluindo a via
"assinar agora com Pix" e a baixa pelo webhook do gateway (modo simulado).
"""
from __future__ import annotations

import random
import re
from datetime import datetime

from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from core.models import Rede
from plataforma.models import Assinatura, ConfiguracaoPlataforma, EventoGateway, Fatura, Pacote
from plataforma.validadores import validar_cnpj

sufixo = datetime.now().strftime("%H%M%S")


def cnpj_valido(base: str) -> str:
    pesos = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])

    def digito(parcial, pesos_do):
        soma = sum(int(d) * p for d, p in zip(parcial, pesos_do, strict=True))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    parcial = base + "0001"
    primeiro = digito(parcial, pesos[0])
    return parcial + primeiro + digito(parcial + primeiro, pesos[1])


print("=" * 78)
print("DEMONSTRACAO: uma academia entra sozinha, paga e comeca a operar")
print("=" * 78)

ConfiguracaoPlataforma.obter()  # garante configuracao + token de webhook
pacotes = {p.codigo: p for p in Pacote.objects.filter(ativo=True, visivel_no_site=True)}
if not pacotes:
    call_command("seed_plataforma", stdout=open("/dev/null", "w"))
    pacotes = {p.codigo: p for p in Pacote.objects.filter(ativo=True)}

print("\n1) SITE PUBLICO")
publico = Client()
for rota in ("vitrine:home", "vitrine:planos", "vitrine:ajuda", "vitrine:cadastro", "vitrine:contato"):
    resposta = publico.get(reverse(rota))
    print(f"   {rota:24} -> HTTP {resposta.status_code}")
print(f"   plano escolhido          -> {pacotes['prata'].nome} R$ {pacotes['prata'].preco_mensal}/mes")


def base_do_cnpj(deslocamento: int = 0) -> str:
    """Base de 8 digitos, diferente a cada execucao e a cada tenant."""
    return f"112{random.randint(10, 99)}{random.randint(100, 999)}{deslocamento}"[:8].ljust(8, "1")


def cadastrar(marcador: str, modalidade: str, pacote, deslocamento: int = 0) -> dict:
    slug = f"demo-{marcador}-{sufixo}"
    cnpj = cnpj_valido(base_do_cnpj(deslocamento))
    formulario = {
        "nome": f"Academia Demo {marcador.title()}",
        "cnpj": cnpj,
        "responsavel": "Dono da Academia",
        "email": f"dono.{marcador}.{sufixo}@exemplo.com",
        "telefone": "51999990000",
        "slug": slug,
        "modalidade": modalidade,
        "aceite": "on",
        "pacote": pacote.codigo,
    }
    cliente = Client()
    resposta = cliente.post(reverse("vitrine:cadastro"), formulario)
    print(f"\n2) CADASTRO [{modalidade}] -> HTTP {resposta.status_code}")
    if resposta.status_code != 302:
        formulario = getattr(resposta, "context", None) or {}
        formulario = formulario.get("form")
        print("   ERRO no formulario:", formulario.errors if formulario else "(sem detalhes)")
        return {}
    rede = Rede.todos.get(slug=slug)
    assinatura = Assinatura.objects.get(rede=rede)
    fatura = Fatura.objects.filter(rede=rede).order_by("-id").first()
    concluido = cliente.get(reverse("vitrine:cadastro_concluido"))
    link = re.search(r"http[^\"]*convite/[^\"<]*", concluido.content.decode())
    print(f"   tenant: {rede.nome} ({rede.slug}) | status={rede.status} | pacote={assinatura.pacote.nome}")
    print(f"   cnpj valido: {validar_cnpj(rede.cnpj)} | trial ate: {assinatura.trial_termina_em}")
    print(f"   link de primeiro acesso: {link.group(0) if link else '(sem link)'}")
    return {"rede": rede, "cliente": cliente, "link": link.group(0) if link else "", "fatura": fatura}


trial = cadastrar("trial", "trial", pacotes["prata"], deslocamento=0)
pago = cadastrar("pix", "pagamento", pacotes["ouro"], deslocamento=2)

if pago.get("fatura"):
    fatura = pago["fatura"]
    print("\n3) COBRANCA (gateway em modo simulado)")
    print(f"   fatura {fatura.numero} | R$ {fatura.valor_final} | vence {fatura.vencimento}")
    print(f"   pix copia e cola: {fatura.pix_copia_cola[:60]}...")

    print("\n4) WEBHOOK DO GATEWAY (idempotente)")
    evento = {
        "id": f"evt-demo-{sufixo}",
        "event": "PAYMENT_RECEIVED",
        "payment": {"id": fatura.gateway_id, "status": "RECEIVED", "value": float(fatura.valor_final)},
    }
    token = ConfiguracaoPlataforma.obter().token_webhook
    cabecalhos = {"asaas-access-token": token} if token else {}
    primeira = publico.post("/plataforma/webhook/asaas/", data=evento,
                            content_type="application/json", headers=cabecalhos)
    segunda = publico.post("/plataforma/webhook/asaas/", data=evento,
                           content_type="application/json", headers=cabecalhos)
    if primeira.status_code != 200:
        print(f"   webhook recusou (HTTP {primeira.status_code}): confira o token configurado")
    pago["rede"].refresh_from_db()
    fatura.refresh_from_db()
    print(f"   1a notificacao: HTTP {primeira.status_code} processado={primeira.json()['processado']}")
    print(f"   2a notificacao: HTTP {segunda.status_code} processado={segunda.json()['processado']} "
          f"({segunda.json()['resultado']})")
    print(f"   fatura -> {fatura.get_status_display()} | tenant -> {pago['rede'].status}")
    print(f"   eventos de gateway registrados: {EventoGateway.objects.count()}")

if trial.get("link"):
    print("\n5) PRIMEIRO ACESSO DO DONO (define a propria senha)")
    novo = Client()
    caminho = trial["link"].split("testserver")[-1]
    pagina = novo.get(caminho)
    print(f"   pagina do convite -> HTTP {pagina.status_code}")
    aceite = novo.post(caminho, {"nome": "Dono da Academia", "senha": "SenhaForteDemo123",
                                "senha2": "SenhaForteDemo123"})
    print(f"   definiu a senha  -> HTTP {aceite.status_code}")
    painel = novo.get(reverse("gestao:visao_geral"))
    plano = novo.get(reverse("gestao:plano"))
    alunos = novo.get(reverse("gestao:alunos"))
    importar = novo.get(reverse("gestao:importar"))
    print("\n6) ACADEMIA OPERANDO NO PROPRIO PAINEL")
    for rotulo, resposta in (("visao geral", painel), ("meu plano", plano), ("alunos", alunos),
                             ("importar", importar)):
        print(f"   {rotulo:24} -> HTTP {resposta.status_code}")

criados = Rede.todos.filter(slug__startswith=f"demo-", slug__endswith=sufixo)
quantidade = criados.count()
created_slugs = list(criados.values_list("slug", flat=True))
criados.delete()
print(f"\n7) LIMPEZA DOS TENANTS DE DEMONSTRACAO: {quantidade} removido(s) {created_slugs}")
print("   (os tenants criados por voce nao sao afetados)")

print("\n" + "=" * 78)
print("FIM DA DEMONSTRACAO")
print("=" * 78)
