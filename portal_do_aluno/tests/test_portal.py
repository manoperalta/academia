"""Testes do portal do aluno: agenda, pagamentos, ficha, preferencias e LGPD."""

from __future__ import annotations

import json
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from agendamento.models import Agendamento
from financeiro.models import Pagamento
from painel.models import Painel
from portal_do_aluno import servicos
from portal_do_aluno.models import ListaDeEspera, PreferenciaDeNotificacao
from portal_do_aluno.servicos import ErroDoPortal
from usuarios.models import FichaSaude

pytestmark = pytest.mark.django_db


def test_turmas_disponiveis_mostram_vagas(aluno, turma):
    linhas = servicos.turmas_disponiveis(aluno)
    assert len(linhas) == 1
    linha = linhas[0]
    assert linha["vagas"] == 2 and linha["cheia"] is False and linha["ja_agendei"] is False


def test_agendar_cria_agendamento_agendado(aluno, turma):
    """O status gravado precisa ser um dos validos do modelo ("pendente" nao era opcao)."""
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    assert agendamento.status == "Agendado"
    assert agendamento.aluno_id == aluno.user_id
    assert servicos.turmas_disponiveis(aluno)[0]["ja_agendei"] is True


def test_agendar_duas_vezes_e_recusado(aluno, turma):
    servicos.agendar(aluno=aluno, turma=turma)
    with pytest.raises(ErroDoPortal):
        servicos.agendar(aluno=aluno, turma=turma)


def test_turma_cheia_manda_para_a_lista_de_espera(aluno, turma, rede, unidade):
    for posicao in range(2):
        login = get_user_model().objects.create_user(
            username=f"cheio{posicao}", password="SenhaForte!23"
        )
        from usuarios.models import Usuario

        ocupante = Usuario.todos.create(
            rede=rede, unidade=unidade, user=login, nome=f"Ocupante {posicao}", status_user="Ativo"
        )
        servicos.agendar(aluno=ocupante, turma=turma)
    with pytest.raises(ErroDoPortal) as erro:
        servicos.agendar(aluno=aluno, turma=turma)
    assert "lista de espera" in str(erro.value)

    servicos.entrar_na_lista_de_espera(aluno=aluno, turma=turma)
    assert ListaDeEspera.objects.filter(turma=turma, aluno=aluno).exists()
    with pytest.raises(ErroDoPortal):
        servicos.entrar_na_lista_de_espera(aluno=aluno, turma=turma)


def test_nao_agenda_turma_de_outra_rede(aluno, outra_rede, responsavel):
    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    alheia = Painel.objects.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        nome="Turma alheia",
        data=timezone.localdate() + timedelta(days=1),
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        numero_de_user=10,
        responsavel=responsavel,
    )
    with pytest.raises(ErroDoPortal):
        servicos.agendar(aluno=aluno, turma=alheia)


def test_nao_agenda_turma_que_ja_passou(aluno, rede, unidade, responsavel):
    passada = Painel.objects.create(
        rede=rede,
        unidade=unidade,
        nome="Turma de ontem",
        data=timezone.localdate() - timedelta(days=1),
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        numero_de_user=10,
        responsavel=responsavel,
    )
    with pytest.raises(ErroDoPortal):
        servicos.agendar(aluno=aluno, turma=passada)


def test_cancelar_avisa_o_proximo_da_fila(aluno, turma, rede, unidade):
    agendamento = servicos.agendar(aluno=aluno, turma=turma)
    login = get_user_model().objects.create_user(username="esperando", password="SenhaForte!23")
    from usuarios.models import Usuario

    esperando = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Aluno na fila", status_user="Ativo"
    )
    servicos.entrar_na_lista_de_espera(aluno=esperando, turma=turma)

    resultado = servicos.cancelar_agendamento(aluno=aluno, agendamento=agendamento)
    agendamento.refresh_from_db()
    assert agendamento.status == "Cancelado"
    assert resultado["avisado"] == "Aluno na fila"
    assert ListaDeEspera.objects.get(turma=turma, aluno=esperando).avisado is True


def test_cancelar_agendamento_de_outro_aluno_e_recusado(aluno, turma, rede, unidade):
    login = get_user_model().objects.create_user(username="dono", password="SenhaForte!23")
    from usuarios.models import Usuario

    dono = Usuario.todos.create(
        rede=rede, unidade=unidade, user=login, nome="Dono", status_user="Ativo"
    )
    agendamento = servicos.agendar(aluno=dono, turma=turma)
    with pytest.raises(ErroDoPortal):
        servicos.cancelar_agendamento(aluno=aluno, agendamento=agendamento)


def test_minhas_faturas_separa_aberto_e_vigente(aluno, rede, unidade, plano):
    hoje = timezone.localdate()
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje - timedelta(days=40),
        data_fim=hoje - timedelta(days=10),
        status="pendente",
        qr_code_text="00020126PIX",
    )
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=hoje,
        data_fim=hoje + timedelta(days=30),
        status="pago",
    )
    faturas = servicos.minhas_faturas(aluno)
    assert faturas["valor_em_aberto"] == Decimal("199.00")
    assert faturas["proxima"] is not None and faturas["proxima"].status == "pago"


def test_ficha_de_saude_cria_e_atualiza(aluno):
    ficha = servicos.salvar_ficha(
        aluno=aluno,
        altura=Decimal("1.70"),
        peso=Decimal("65.00"),
        restricoes="joelho",
        usa_medicamento=True,
        qual_medicamento="losartana",
    )
    assert ficha.restricoes == "joelho" and ficha.usa_medicamento is True
    atualizada = servicos.salvar_ficha(
        aluno=aluno, altura=Decimal("1.70"), peso=Decimal("64.00"), restricoes="joelho e ombro"
    )
    assert FichaSaude.todos.filter(usuario=aluno).count() == 1
    assert atualizada.restricoes == "joelho e ombro" and atualizada.peso == Decimal("64.00")


def test_preferencias_padrao_e_gravacao(aluno):
    padrao = servicos.preferencias_do_aluno(aluno)
    assert padrao.canal == PreferenciaDeNotificacao.Canal.WHATSAPP
    assert padrao.avisar_vencimento is True
    salvas = servicos.salvar_preferencias(
        aluno=aluno,
        canal="email",
        avisar_vencimento=False,
        avisar_aula=True,
        receber_novidades=True,
    )
    assert salvas.canal == "email" and salvas.avisar_vencimento is False
    with pytest.raises(ErroDoPortal):
        servicos.salvar_preferencias(aluno=aluno, canal="pombo")


def test_meus_dados_traz_tudo_do_titular(aluno, turma, rede, unidade, plano):
    servicos.agendar(aluno=aluno, turma=turma)
    servicos.salvar_ficha(
        aluno=aluno, altura=Decimal("1.70"), peso=Decimal("65.00"), restricoes="joelho"
    )
    Pagamento.objects.create(
        rede=rede,
        unidade=unidade,
        usuario=aluno.user,
        plano=plano,
        valor_pago=Decimal("199.00"),
        data_inicio=timezone.localdate(),
        data_fim=timezone.localdate() + timedelta(days=30),
        status="pago",
    )
    dados = servicos.meus_dados(aluno)
    assert dados["titular"]["nome"] == "Aluna Portal"
    assert dados["ficha_de_saude"]["restricoes"] == "joelho"
    assert len(dados["pagamentos"]) == 1
    assert json.dumps(dados)  # serializavel


def test_telas_do_portal_abrem(cliente_aluno, turma):
    for rota in ("portal:agenda", "portal:pagamentos", "portal:ficha", "portal:perfil"):
        assert cliente_aluno.get(reverse(rota)).status_code == 200, rota


def test_agendar_e_cancelar_pelas_telas(cliente_aluno, aluno, turma):
    resposta = cliente_aluno.post(reverse("portal:agendar", args=[turma.pk]))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("portal:agenda"), resposta["Location"]
    corpo = cliente_aluno.get(resposta["Location"]).content.decode()
    agendamento = Agendamento.objects.filter(aluno=aluno.user, painel=turma).first()
    assert agendamento is not None, corpo[-900:]
    assert agendamento.status == "Agendado"
    assert (
        cliente_aluno.post(
            reverse("portal:cancelar_agendamento", args=[agendamento.pk])
        ).status_code
        == 302
    )
    agendamento.refresh_from_db()
    assert agendamento.status == "Cancelado"


def test_baixar_meus_dados_pela_tela(cliente_aluno, aluno):
    resposta = cliente_aluno.get(reverse("portal:meus_dados"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/json"
    assert "attachment" in resposta["Content-Disposition"]
    assert "Aluna Portal" in resposta.content.decode()


def test_turma_de_outra_rede_nao_aparece_na_agenda(aluno, outra_rede, cliente_aluno, responsavel):
    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    Painel.objects.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        nome="Turma de outra academia",
        data=timezone.localdate() + timedelta(days=1),
        hora_inicio=time(8, 0),
        hora_fim=time(9, 0),
        numero_de_user=10,
        responsavel=responsavel,
    )
    corpo = cliente_aluno.get(reverse("portal:agenda")).content.decode()
    assert "Turma de outra academia" not in corpo


def test_quem_nao_e_aluno_recebe_404(client, db, rede):
    login = get_user_model().objects.create_user(username="sem.perfil", password="SenhaForte!23")
    client.force_login(login)
    assert client.get(reverse("portal:agenda")).status_code == 404
