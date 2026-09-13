"""Comandos de gestao da plataforma (o que roda no cron)."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from plataforma.models import Assinatura, EventoCobranca, Fatura, Pacote
from plataforma.servicos import gerar_fatura


def test_seed_cria_os_tres_pacotes(db):
    call_command("seed_plataforma", stdout=StringIO())
    pacotes = {p.codigo: p for p in Pacote.objects.all()}
    assert set(pacotes) == {"prata", "bronze", "ouro"}
    assert pacotes["prata"].limite_alunos == 100
    assert pacotes["prata"].limite_professores == 5
    assert pacotes["bronze"].limite_alunos == 150
    assert pacotes["ouro"].limite_alunos is None
    assert pacotes["ouro"].tem_modulo("api") is True


def test_seed_e_idempotente(db):
    call_command("seed_plataforma", stdout=StringIO())
    call_command("seed_plataforma", stdout=StringIO())
    assert Pacote.objects.count() == 3


def test_seed_cria_trial_para_redes_sem_assinatura(db, rede):
    call_command("seed_plataforma", stdout=StringIO())
    assinatura = Assinatura.objects.get(rede=rede)
    assert assinatura.pacote.codigo == "ouro"
    assert assinatura.em_trial is True
    rede.refresh_from_db()
    assert rede.status == "trial"


def test_seed_respeita_precos_informados(db):
    call_command(
        "seed_plataforma", "--prata", "149", "--bronze", "249", "--ouro", "499", stdout=StringIO()
    )
    assert Pacote.objects.get(codigo="prata").preco_mensal == 149


def test_gerar_faturas_do_comando(db, rede, assinatura):
    assinatura.renovacao_em = timezone.localdate()
    assinatura.save()
    saida = StringIO()
    call_command("gerar_faturas", stdout=saida)
    assert "FAT-" in saida.getvalue()
    assert Fatura.objects.filter(rede=rede).count() == 1


def test_gerar_faturas_sem_cobranca(db, rede, assinatura):
    assinatura.renovacao_em = timezone.localdate()
    assinatura.save()
    call_command("gerar_faturas", "--sem-cobranca", stdout=StringIO())
    fatura = Fatura.objects.get(rede=rede)
    assert fatura.gateway == ""


def test_rodar_regua_do_comando(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=2)
    fatura.save()
    saida = StringIO()
    call_command("rodar_regua", stdout=saida)
    assert "disparos:" in saida.getvalue()
    assert EventoCobranca.objects.filter(fatura=fatura).exists()


def test_rodar_regua_com_data_de_referencia(db, rede, assinatura):
    fatura = gerar_fatura(assinatura)
    alvo = (fatura.vencimento + timedelta(days=12)).isoformat()
    call_command("rodar_regua", "--hoje", alvo, stdout=StringIO())
    rede.refresh_from_db()
    assert rede.status == "somente_leitura"
