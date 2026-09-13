"""Testes das telas finais do inventario: comparativo de unidades, auditoria e inadimplencia."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from cobranca import servicos as servicos_de_cobranca
from cobranca.models import CobrancaRecorrente
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from financeiro.models import Pagamento, Plano
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db
SENHA = "SenhaForteFinal!23"


@pytest.fixture
def rede(db):
    return Rede.todos.create(nome="Rede Comparativa", slug="rede-comparativa", status="ativo")


@pytest.fixture
def unidades(db, rede):
    return [
        Unidade.objects.create(
            rede=rede, nome="Centro", codigo="centro", tipo="propria", status="ativa"
        ),
        Unidade.objects.create(
            rede=rede, nome="Zona Norte", codigo="norte", tipo="franqueada", status="ativa"
        ),
    ]


@pytest.fixture
def plano(db, rede, unidades):
    return Plano.objects.create(
        rede=rede, unidade=unidades[0], nome="Mensal", tipo="mensal", valor=Decimal("199.00")
    )


@pytest.fixture
def aluno(db, rede, unidades, plano):
    login = get_user_model().objects.create_user(
        username="aluno.final", password=SENHA, email="aluno.final@x.com"
    )
    perfil = Usuario.todos.create(
        rede=rede, unidade=unidades[0], user=login, nome="Aluno Final", status_user="Ativo"
    )
    hoje = timezone.localdate()
    # Centro: pagamento vigente e um vencido; Zona Norte: so um vigente menor
    Pagamento.objects.create(
        rede=rede,
        unidade=unidades[0],
        usuario=login,
        plano=plano,
        valor_pago=Decimal("400.00"),
        data_inicio=hoje.replace(day=1),
        data_fim=hoje + timedelta(days=20),
        status="pago",
    )
    Pagamento.objects.create(
        rede=rede,
        unidade=unidades[0],
        usuario=login,
        plano=plano,
        valor_pago=Decimal("100.00"),
        data_inicio=hoje - timedelta(days=60),
        data_fim=hoje - timedelta(days=30),
        status="pendente",
    )
    outro_login = get_user_model().objects.create_user(
        username="aluno.norte", password=SENHA, email="aluno.norte@x.com"
    )
    Usuario.todos.create(
        rede=rede, unidade=unidades[1], user=outro_login, nome="Aluno Norte", status_user="Ativo"
    )
    Pagamento.objects.create(
        rede=rede,
        unidade=unidades[1],
        usuario=outro_login,
        plano=plano,
        valor_pago=Decimal("150.00"),
        data_inicio=hoje.replace(day=1),
        data_fim=hoje + timedelta(days=20),
        status="pago",
    )
    return perfil


@pytest.fixture
def cliente_painel(client, rede):
    login = get_user_model().objects.create_user(
        username="admin.final", password=SENHA, email="admin.final@x.com"
    )
    VinculoUsuario.todos.create(usuario=login, rede=rede, papel=Papel.ADMIN_REDE, ativo=True)
    client.force_login(login)
    return client


# ------------------------------------------------------------------ comparativo


def test_comparativo_rankeia_por_receita_e_mostra_inadimplencia(
    cliente_painel, rede, aluno, unidades
):
    resposta = cliente_painel.get(reverse("rede:comparativo"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Centro" in corpo and "Zona Norte" in corpo
    assert "400,00" in corpo or "400.00" in corpo
    assert corpo.index("Centro") < corpo.index("Zona Norte"), "quem fatura mais aparece primeiro"
    assert "100" in corpo, "o valor vencido aparece no comparativo"


# ------------------------------------------------------------------ auditoria da plataforma


@pytest.fixture
def cliente_plataforma(db):
    """Equipe da SafeStack com o segundo fator confirmado (exigido pelo middleware)."""
    from django.test import Client

    from governanca.models import Dispositivo2FA

    equipe = get_user_model().objects.create_user(
        username="equipe.auditoria", password=SENHA, email="equipe@safestack.com.br", is_staff=True
    )
    Dispositivo2FA.objects.create(
        usuario=equipe, segredo="JBSWY3DPEHPK3PXP", confirmado_em=timezone.now()
    )
    cliente = Client()
    cliente.force_login(equipe)
    sessao = cliente.session
    sessao["dois_fatores_ok"] = timezone.now().timestamp()
    sessao.save()
    return cliente


def test_auditoria_da_plataforma_lista_e_exporta(cliente_plataforma, db, rede):
    from api.models import RegistroAuditoria

    equipe = get_user_model().objects.get(username="equipe.auditoria")
    RegistroAuditoria.objects.create(
        rede=rede,
        usuario=equipe,
        acao=RegistroAuditoria.Acao.ALTERAR,
        entidade="rede",
        entidade_id=str(rede.pk),
    )
    client = cliente_plataforma

    lista = client.get(reverse("plataforma:auditoria"))
    assert lista.status_code == 200
    assert "Auditoria da plataforma" in lista.content.decode()

    csv_resposta = client.get(reverse("plataforma:auditoria"), {"formato": "csv"})
    assert csv_resposta.status_code == 200
    assert csv_resposta["Content-Type"].startswith("text/csv")
    assert "attachment" in csv_resposta["Content-Disposition"]
    assert "rede" in csv_resposta.content.decode()


def test_auditoria_nao_abre_para_usuario_comum(cliente_painel):
    """Quem nao e da equipe da SafeStack nao entra no painel da plataforma."""
    resposta = cliente_painel.get(reverse("plataforma:auditoria"))
    assert resposta.status_code in (302, 403)


# ------------------------------------------------------------------ inadimplencia


def test_inadimplencia_agrupa_por_faixa_e_filtra(cliente_painel, rede, unidades, aluno):
    hoje = timezone.localdate()
    cobranca = CobrancaRecorrente.objects.create(
        rede=rede,
        unidade=unidades[0],
        aluno=aluno,
        competencia=hoje.replace(day=1),
        valor=Decimal("199.00"),
        vencimento=hoje - timedelta(days=20),
    )
    outra = CobrancaRecorrente.objects.create(
        rede=rede,
        unidade=unidades[1],
        aluno=aluno,
        competencia=(hoje - timedelta(days=40)).replace(day=1),
        valor=Decimal("199.00"),
        vencimento=hoje - timedelta(days=40),
    )
    resumo = servicos_de_cobranca.resumo_da_inadimplencia(rede)
    assert resumo["quantidade_vencidas"] == 2
    assert resumo["valor_vencido"] == Decimal("398.00")
    assert resumo["por_faixa"]["16_a_30"]["quantidade"] == 1
    assert resumo["por_faixa"]["mais_de_30"]["quantidade"] == 1
    assert resumo["mais_antiga"].pk == outra.pk

    pagina = cliente_painel.get(reverse("cobranca:inadimplencia"))
    assert pagina.status_code == 200
    assert "Inadimplência" in pagina.content.decode()

    filtrado = cliente_painel.get(reverse("cobranca:inadimplencia"), {"faixa": "mais_de_30"})
    assert filtrado.status_code == 200
    linhas = servicos_de_cobranca.lista_de_inadimplentes(rede, faixa="mais_de_30")
    assert [linha["cobranca"].pk for linha in linhas] == [outra.pk]
    assert linhas[0]["dias"] >= 30
    assert linhas[0]["mensagem"]
    assert cobranca.pk not in [linha["cobranca"].pk for linha in linhas]
