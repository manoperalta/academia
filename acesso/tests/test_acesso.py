"""Testes do controle de acesso, da catraca e da conciliacao com parceiros."""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from acesso import servicos
from acesso.models import (
    ExtratoDeParceiro,
    PlanoDeParceiro,
    RegistroDeAcesso,
)
from acesso.servicos import ErroDeAcesso

pytestmark = pytest.mark.django_db


def quantos_checkins(aluno) -> int:
    from area_do_aluno.models import CheckinDoAluno

    return CheckinDoAluno.objects.filter(aluno=aluno).count()


# ------------------------------------------------------------------ decisao


def test_libera_com_mensalidade_em_dia_e_gera_checkin(
    rede, unidade, aluno, plano_em_dia, credencial
):
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert resultado["liberado"] is True
    assert resultado["checkin_gerado"] is True
    assert resultado["registro"].liberado is True
    assert quantos_checkins(aluno) == 1


def test_nega_com_mensalidade_vencida_e_explica(rede, unidade, aluno, credencial):
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert resultado["liberado"] is False
    assert "vigencia" in resultado["motivo"] or "vencida" in resultado["motivo"]
    assert quantos_checkins(aluno) == 0


def test_credencial_cancelada_nega(rede, unidade, aluno, plano_em_dia, credencial):
    servicos.cancelar_credencial(credencial)
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert resultado["liberado"] is False
    assert "cancelada" in resultado["motivo"]


def test_aluno_inativo_nega(rede, unidade, aluno, plano_em_dia, credencial):
    aluno.status_user = "Inativo"
    aluno.save(update_fields=["status_user"])
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert resultado["liberado"] is False
    assert "situacao" in resultado["motivo"]


def test_credencial_de_outra_rede_nao_e_reconhecida(rede, outra_rede, unidade, aluno, plano_em_dia):
    from django.contrib.auth import get_user_model

    from core.models import Unidade
    from usuarios.models import Usuario

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Alheia", codigo="alheia")
    login = get_user_model().objects.create_user(
        username="alheio.acesso", password="SenhaAlheia!23"
    )
    outro_aluno = Usuario.todos.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        user=login,
        nome="Aluno Alheio",
        status_user="Ativo",
    )
    servicos.emitir_credencial(aluno=outro_aluno, codigo="CARD-ALHEIO")
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-ALHEIO")
    assert resultado["liberado"] is False
    assert "nao reconhecida" in resultado["motivo"]


def test_anti_passback_nao_duplica_o_checkin(rede, unidade, aluno, plano_em_dia, credencial):
    primeiro = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    segundo = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert primeiro["liberado"] and segundo["liberado"]
    assert segundo["duplicado"] is True
    assert segundo["checkin_gerado"] is False
    assert quantos_checkins(aluno) == 1


def test_entrada_em_outra_unidade_fica_marcada_como_itinerante(
    rede, filial, aluno, plano_em_dia, credencial
):
    resultado = servicos.decidir_acesso(rede=rede, unidade=filial, codigo="CARD-0001")
    assert resultado["liberado"] is True
    assert resultado["registro"].itinerante is True


def test_dispositivo_inativo_nega(rede, unidade, aluno, plano_em_dia, credencial, dispositivo):
    dispositivo.ativo = False
    dispositivo.save(update_fields=["ativo"])
    resultado = servicos.decidir_acesso(
        rede=rede, unidade=unidade, codigo="CARD-0001", dispositivo=dispositivo
    )
    assert resultado["liberado"] is False
    assert "inativo" in resultado["motivo"]


# ------------------------------------------------------------------ endpoint da catraca


def test_catraca_libera_com_token_valido(
    client, rede, unidade, aluno, plano_em_dia, dispositivo, credencial
):
    resposta = client.post(
        reverse("acesso:integracao"),
        data=json.dumps({"codigo": "CARD-0001", "token": "token-de-teste-123"}),
        content_type="application/json",
        HTTP_X_DISPOSITIVO="catraca-1",
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["liberado"] is True, corpo  # a mensagem mostra o motivo da negativa
    assert corpo["aluno"] == "Aluno do Acesso"


def test_catraca_recusa_token_invalido(client, dispositivo):
    resposta = client.post(
        reverse("acesso:integracao"),
        data=json.dumps({"codigo": "CARD-0001", "token": "errado"}),
        content_type="application/json",
        HTTP_X_DISPOSITIVO="catraca-1",
    )
    assert resposta.status_code == 403
    assert "token" in resposta.json()["motivo"]


def test_catraca_recusa_dispositivo_desconhecido(client, db):
    resposta = client.post(
        reverse("acesso:integracao"),
        data=json.dumps({"codigo": "X"}),
        content_type="application/json",
        HTTP_X_DISPOSITIVO="nao-existe",
    )
    assert resposta.status_code == 403


# ------------------------------------------------------------------ parceiros


def _csv_do_parceiro(linhas: str) -> str:
    return "data;codigo;nome;valor\n" + linhas


@pytest.fixture
def plano_de_parceiro(rede):
    return PlanoDeParceiro.objects.create(
        rede=rede,
        parceiro=PlanoDeParceiro.Parceiro.WELLHUB,
        nome_no_parceiro="Wellhub Basic",
        valor_por_acesso=Decimal("12.00"),
        percentual_do_parceiro=Decimal("20.00"),
    )


def test_importar_extrato_le_csv_com_ponto_e_virgula(rede, plano_de_parceiro):
    extrato = servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=timezone.localdate().replace(day=1),
        conteudo=_csv_do_parceiro(
            "01/09/2026;CARD-0001;Aluno do Acesso;12,00\n02/09/2026;CARD-0002;Outro Aluno;12,00\n"
        ),
        nome_do_arquivo="wellhub-set.csv",
    )
    assert extrato.total_de_acessos == 2
    assert extrato.valor_total == Decimal("24.00")
    assert extrato.valor_esperado_pela_rede == Decimal("19.20")  # 20% fica com o parceiro


def test_importar_extrato_sem_coluna_obrigatoria_falha(rede, plano_de_parceiro):
    with pytest.raises(ErroDeAcesso):
        servicos.importar_extrato(
            plano_de_parceiro=plano_de_parceiro,
            competencia=timezone.localdate().replace(day=1),
            conteudo="dia;quem;quanto\n01/09/2026;X;12,00\n",
        )


def test_importar_extrato_duplicado_da_competencia_falha(rede, plano_de_parceiro):
    competencia = timezone.localdate().replace(day=1)
    servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=competencia,
        conteudo=_csv_do_parceiro("01/09/2026;CARD-1;X;12,00\n"),
    )
    with pytest.raises(ErroDeAcesso):
        servicos.importar_extrato(
            plano_de_parceiro=plano_de_parceiro,
            competencia=competencia,
            conteudo=_csv_do_parceiro("02/09/2026;CARD-2;Y;12,00\n"),
        )


def test_conciliacao_aponta_cobranca_sem_acesso_e_acesso_nao_faturado(
    rede, unidade, aluno, plano_em_dia, credencial, plano_de_parceiro
):
    hoje = timezone.localdate()
    # um acesso real, liberado hoje, que NAO esta no extrato -> nao faturado
    servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    extrato = servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=hoje.replace(day=1),
        conteudo=_csv_do_parceiro(f"{hoje:%d/%m/%Y};CARD-INEXISTENTE;Ninguem;12,00\n"),
    )
    resultado = servicos.conciliar_extrato(extrato)
    assert resultado["conciliadas"] == 0
    assert len(resultado["sem_acesso"]) == 1
    assert len(resultado["nao_faturados"]) == 1
    extrato.refresh_from_db()
    assert extrato.situacao == ExtratoDeParceiro.Situacao.COM_DIVERGENCIA
    linha = extrato.linhas.first()
    assert linha.conciliado is False and "sem acesso" in linha.divergencia


def test_conciliacao_casa_a_cobranca_com_o_acesso_do_dia(
    rede, unidade, aluno, plano_em_dia, credencial, plano_de_parceiro
):
    hoje = timezone.localdate()
    servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    extrato = servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=hoje.replace(day=1),
        conteudo=_csv_do_parceiro(f"{hoje:%d/%m/%Y};CARD-0001;Aluno do Acesso;12,00\n"),
    )
    resultado = servicos.conciliar_extrato(extrato)
    assert resultado["conciliadas"] == 1
    assert resultado["sem_acesso"] == [] and resultado["nao_faturados"] == []
    extrato.refresh_from_db()
    assert extrato.situacao == ExtratoDeParceiro.Situacao.CONCILIADO


def test_simulacao_da_conciliacao_nao_grava(
    rede, unidade, aluno, plano_em_dia, credencial, plano_de_parceiro
):
    hoje = timezone.localdate()
    extrato = servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=hoje.replace(day=1),
        conteudo=_csv_do_parceiro(f"{hoje:%d/%m/%Y};SEM-ACESSO;X;12,00\n"),
    )
    resultado = servicos.conciliar_extrato(extrato, dry_run=True)
    assert resultado["dry_run"] is True and len(resultado["sem_acesso"]) == 1
    extrato.refresh_from_db()
    assert extrato.situacao == ExtratoDeParceiro.Situacao.IMPORTADO
    assert extrato.linhas.first().conciliado is False


def test_autorizacao_do_parceiro_libera_quem_nao_tem_mensalidade(
    rede, unidade, aluno, credencial, plano_de_parceiro
):
    hoje = timezone.localdate()
    servicos.importar_extrato(
        plano_de_parceiro=plano_de_parceiro,
        competencia=hoje.replace(day=1),
        conteudo=_csv_do_parceiro(f"{hoje:%d/%m/%Y};CARD-0001;Aluno do Acesso;12,00\n"),
    )
    resultado = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert resultado["liberado"] is True


def test_limite_do_parceiro_e_respeitado(rede, unidade, aluno, credencial):
    hoje = timezone.localdate()
    plano = PlanoDeParceiro.objects.create(
        rede=rede,
        parceiro=PlanoDeParceiro.Parceiro.TOTALPASS,
        nome_no_parceiro="TotalPass 1x",
        valor_por_acesso=Decimal("10.00"),
        percentual_do_parceiro=Decimal("10.00"),
        limite_de_acessos_por_mes=1,
    )
    servicos.importar_extrato(
        plano_de_parceiro=plano,
        competencia=hoje.replace(day=1),
        conteudo=_csv_do_parceiro(f"{hoje:%d/%m/%Y};CARD-0001;Aluno do Acesso;10,00\n"),
    )
    primeiro = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001")
    assert primeiro["liberado"] is True
    # segundo acesso no mesmo dia (fora da janela de anti-passback) bate no limite
    from django.utils import timezone as tz

    depois = tz.now() + timedelta(minutes=10)
    segundo = servicos.decidir_acesso(rede=rede, unidade=unidade, codigo="CARD-0001", agora=depois)
    assert segundo["liberado"] is False
    assert "limite" in segundo["motivo"]


# ------------------------------------------------------------------ telas


def test_telas_do_acesso_abrem(cliente_painel, rede, unidade, credencial, plano_em_dia):
    for rota in ("acesso:painel", "acesso:registros", "acesso:credenciais", "acesso:parceiros"):
        assert cliente_painel.get(reverse(rota)).status_code == 200, rota


def test_emite_credencial_pela_tela(cliente_painel, rede, aluno):
    from acesso.models import CredencialDeAcesso

    resposta = cliente_painel.post(
        reverse("acesso:emitir_credencial"),
        {"aluno": aluno.pk, "codigo": "CARD-9999", "tipo": "cartao"},
    )
    assert resposta.status_code == 302
    assert CredencialDeAcesso.objects.filter(rede=rede, codigo="CARD-9999").exists()


def test_libera_manualmente_pela_tela(cliente_painel, rede, unidade, aluno, plano_em_dia):
    resposta = cliente_painel.post(
        reverse("acesso:liberar"),
        {"aluno": aluno.pk, "unidade": unidade.pk, "motivo": "esqueceu o cartao"},
    )
    assert resposta.status_code == 302
    registro = RegistroDeAcesso.objects.filter(rede=rede, aluno=aluno).first()
    assert registro is not None and registro.origem == RegistroDeAcesso.Origem.MANUAL


def test_nao_ve_extrato_de_outra_rede(cliente_painel, outra_rede):
    from acesso.models import PlanoDeParceiro as Plano

    outro_plano = Plano.objects.create(
        rede=outra_rede, parceiro="wellhub", nome_no_parceiro="Wellhub de outro"
    )
    extrato = servicos.importar_extrato(
        plano_de_parceiro=outro_plano,
        competencia=timezone.localdate().replace(day=1),
        conteudo=_csv_do_parceiro("01/09/2026;X;Y;12,00\n"),
    )
    assert cliente_painel.get(reverse("acesso:extrato", args=[extrato.pk])).status_code == 404


def test_aluno_nao_entra_no_controle_de_acesso(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("acesso:painel")).status_code == 403
