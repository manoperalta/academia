"""Testes do funil de captacao e do risco de evasao."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from relacionamento import servicos
from relacionamento.models import InteracaoComLead, Lead, OrigemDoLead, PerfilDeRisco
from relacionamento.servicos import ErroDeRelacionamento
from relacionamento.tests.conftest import pagar, responder_detrator, treinar

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ captacao


def test_lead_registrado_entra_no_funil(rede, unidade):
    lead = servicos.registrar_lead(
        rede=rede,
        unidade=unidade,
        nome="Maria Interessada",
        telefone="(51) 99999-0000",
        origem=OrigemDoLead.INSTAGRAM,
        interesse="Mensal Ouro",
    )
    assert lead.situacao == Lead.Situacao.NOVO
    assert lead.esta_aberto is True


def test_lead_repetido_no_telefone_e_reaproveitado(rede, unidade):
    primeiro = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Maria", telefone="51 99999-0000"
    )
    segundo = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Maria de novo", telefone="51999990000"
    )
    assert primeiro.pk == segundo.pk, "nao cria lead duplicado com o mesmo telefone"


def test_lead_sem_nome_e_recusado(rede):
    with pytest.raises(ErroDeRelacionamento):
        servicos.registrar_lead(rede=rede, nome="   ")


def test_interacao_avanca_a_situacao_e_agenda_retorno(rede, unidade):
    lead = servicos.registrar_lead(rede=rede, unidade=unidade, nome="Joao", telefone="5199")
    amanha = timezone.localdate() + timedelta(days=1)
    servicos.registrar_interacao(
        lead=lead,
        tipo=InteracaoComLead.Tipo.WHATSAPP,
        resumo="Falei do plano Ouro",
        proximo_contato_em=amanha,
    )
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.CONTATADO
    assert lead.proximo_contato_em == amanha


def test_visita_registrada_avanca_para_visitou(rede, unidade):
    lead = servicos.registrar_lead(rede=rede, unidade=unidade, nome="Ana", telefone="5188")
    servicos.registrar_interacao(
        lead=lead, tipo=InteracaoComLead.Tipo.VISITA, resumo="Conheceu a academia"
    )
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.VISITOU


def test_converter_lead_guarda_o_aluno_e_recusa_a_segunda_vez(rede, unidade, aluno):
    lead = servicos.registrar_lead(rede=rede, unidade=unidade, nome="Carlos", telefone="5177")
    servicos.converter_lead(lead=lead, aluno=aluno)
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.MATRICULADO
    assert lead.aluno == aluno and lead.convertido_em is not None
    assert lead.dias_ate_matricular is not None
    with pytest.raises(ErroDeRelacionamento):
        servicos.converter_lead(lead=lead, aluno=aluno)


def test_perder_lead_exige_motivo(rede, unidade):
    lead = servicos.registrar_lead(rede=rede, unidade=unidade, nome="Paula", telefone="5166")
    with pytest.raises(ErroDeRelacionamento):
        servicos.marcar_perdido(lead=lead, motivo="  ")
    servicos.marcar_perdido(lead=lead, motivo="Achou caro")
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.PERDIDO
    assert lead.motivo_da_perda == "Achou caro"


def test_matricular_lead_cria_login_sem_senha_utilizavel(rede, unidade):
    lead = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Rita Souza", telefone="5155", email="rita@exemplo.com"
    )
    lead, perfil = servicos.matricular_lead(lead=lead)
    assert perfil.nome == "Rita Souza"
    assert perfil.user.username == "rita"
    assert perfil.user.has_usable_password() is False, "aluno define a senha no primeiro acesso"
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.MATRICULADO and lead.aluno == perfil


def test_matricular_lead_com_login_repetido_ganha_sufixo(rede, unidade):
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(username="rita", password="SenhaForte!23")
    lead = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Rita", email="rita@exemplo.com"
    )
    _lead, perfil = servicos.matricular_lead(lead=lead)
    assert perfil.user.username == "rita2"


def test_funil_conta_situacoes_e_conversao_por_origem(rede, unidade, aluno):
    for origem in (OrigemDoLead.INSTAGRAM, OrigemDoLead.INSTAGRAM, OrigemDoLead.PORTA):
        servicos.registrar_lead(
            rede=rede,
            unidade=unidade,
            nome=f"Lead {origem} {id(origem)}",
            telefone="",
            origem=origem,
        )
    convertido = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Convertido", telefone="", origem=OrigemDoLead.INSTAGRAM
    )
    servicos.converter_lead(lead=convertido, aluno=aluno)
    resumo = servicos.funil(rede)
    assert resumo["total"] == 4
    assert resumo["convertidos"] == 1
    assert resumo["taxa_de_conversao"] == 25.0
    instagram = next(linha for linha in resumo["por_origem"] if linha["origem"] == "Instagram")
    assert instagram["leads"] == 3 and instagram["matriculados"] == 1
    assert instagram["taxa"] == 33.3


# ------------------------------------------------------------------ retencao


def test_risco_critico_para_ausente_com_mensalidade_vencida_e_nota_baixa(
    rede, unidade, aluno, plano
):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    treinar(aluno, unidade, dias_atras=45)
    responder_detrator(aluno, rede, unidade)
    conta = servicos.calcular_risco(aluno)
    assert conta["pontuacao"] >= 75
    assert conta["faixa"] == PerfilDeRisco.Faixa.CRITICO
    assert conta["acao"] == PerfilDeRisco.Acao.OFERTA_RETENCAO
    texto = " | ".join(conta["motivos"])
    assert "sem treinar" in texto and "vencida" in texto and "detrator" in texto


def test_risco_baixo_para_quem_treinou_e_esta_em_dia(rede, unidade, aluno, plano):
    pagar(rede, unidade, aluno, plano, vence_em=20)
    treinar(aluno, unidade, dias_atras=1)
    conta = servicos.calcular_risco(aluno)
    assert conta["faixa"] == PerfilDeRisco.Faixa.BAIXO
    assert conta["pontuacao"] <= 24
    assert any("Treinou" in motivo for motivo in conta["motivos"])


def test_simulacao_do_recalculo_nao_grava(rede, unidade, aluno, plano):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    resultado = servicos.atualizar_perfis_de_risco(rede, dry_run=True)
    assert resultado["dry_run"] is True
    assert resultado["criados"] == 1
    assert resultado["mudancas"], "a simulacao mostra o que mudaria"
    assert PerfilDeRisco.objects.count() == 0, "simulacao nao grava"


def test_recalculo_grava_perfil_e_reaproveita_o_registro(rede, unidade, aluno, plano):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    servicos.atualizar_perfis_de_risco(rede)
    perfil = PerfilDeRisco.objects.get(aluno=aluno)
    # Sem check-in nenhum (+35) e com mensalidade vencida ha 40 dias (+30): 65 pontos, faixa alta.
    assert perfil.pontuacao == 65
    assert perfil.faixa == PerfilDeRisco.Faixa.ALTO
    assert any("Nunca registrou check-in" in motivo for motivo in perfil.motivos)
    treinar(aluno, unidade, dias_atras=0)
    servicos.atualizar_perfis_de_risco(rede)
    assert PerfilDeRisco.objects.filter(aluno=aluno).count() == 1
    perfil.refresh_from_db()
    assert any("Treinou" in motivo for motivo in perfil.motivos)


def test_desfecho_e_resumo_da_retencao(rede, unidade, aluno, plano):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    servicos.atualizar_perfis_de_risco(rede)
    perfil = PerfilDeRisco.objects.get(aluno=aluno)
    servicos.registrar_desfecho(
        perfil=perfil,
        desfecho=PerfilDeRisco.Desfecho.RECUPERADO,
        observacoes="Voltou depois da ligacao",
    )
    perfil.refresh_from_db()
    assert perfil.desfecho == PerfilDeRisco.Desfecho.RECUPERADO
    with pytest.raises(ErroDeRelacionamento):
        servicos.registrar_desfecho(perfil=perfil, desfecho="inventado")
    resumo = servicos.resumo_da_retencao(rede)
    assert resumo["total"] == 1 and resumo["recuperados"] == 1


# ------------------------------------------------------------------ telas


def test_telas_do_crm_abrem(cliente_painel, rede, unidade):
    servicos.registrar_lead(rede=rede, unidade=unidade, nome="Maria", telefone="5199")
    for nome_rota in ("relacionamento:funil", "relacionamento:leads", "relacionamento:retencao"):
        resposta = cliente_painel.get(reverse(nome_rota))
        assert resposta.status_code == 200, nome_rota


def test_registrar_interacao_pela_tela(cliente_painel, rede, unidade):
    lead = servicos.registrar_lead(rede=rede, unidade=unidade, nome="Bia", telefone="5144")
    resposta = cliente_painel.post(
        reverse("relacionamento:interacao", args=[lead.pk]),
        {"tipo": "whatsapp", "resumo": "Mandei os valores", "resultado": "Pediu para ligar amanha"},
    )
    assert resposta.status_code == 302
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.CONTATADO
    assert lead.interacoes.count() == 1
    assert cliente_painel.get(reverse("relacionamento:lead", args=[lead.pk])).status_code == 200


def test_converter_pela_tela_cria_a_matricula(cliente_painel, rede, unidade):
    lead = servicos.registrar_lead(
        rede=rede, unidade=unidade, nome="Vitor Hugo", telefone="5133", email="vitor@exemplo.com"
    )
    resposta = cliente_painel.post(reverse("relacionamento:converter", args=[lead.pk]))
    assert resposta.status_code == 302
    lead.refresh_from_db()
    assert lead.situacao == Lead.Situacao.MATRICULADO and lead.aluno is not None


def test_simulacao_pela_tela_avisa_que_nada_foi_gravado(
    cliente_painel, rede, unidade, aluno, plano
):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    resposta = cliente_painel.post(reverse("relacionamento:atualizar_risco"), {"dry_run": "1"})
    assert resposta.status_code == 200
    assert "nada foi gravado" in resposta.content.decode()
    assert PerfilDeRisco.objects.count() == 0


def test_desfecho_pela_tela(cliente_painel, rede, unidade, aluno, plano):
    pagar(rede, unidade, aluno, plano, vence_em=-40)
    servicos.atualizar_perfis_de_risco(rede)
    perfil = PerfilDeRisco.objects.get(aluno=aluno)
    resposta = cliente_painel.post(
        reverse("relacionamento:desfecho", args=[perfil.pk]),
        {"desfecho": "cancelou", "observacoes": "Mudou de bairro"},
    )
    assert resposta.status_code == 302
    perfil.refresh_from_db()
    assert perfil.desfecho == PerfilDeRisco.Desfecho.CANCELOU


def test_lead_de_outra_rede_nao_abre(cliente_painel, outra_rede):
    alheio = servicos.registrar_lead(rede=outra_rede, nome="Lead de outra rede")
    assert cliente_painel.get(reverse("relacionamento:lead", args=[alheio.pk])).status_code == 404


def test_aluno_nao_entra_no_crm_nem_na_retencao(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("relacionamento:funil")).status_code == 403
    assert client.get(reverse("relacionamento:retencao")).status_code == 403
