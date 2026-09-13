"""Telas do painel: LGPD, dominio, seguranca e o painel da plataforma (Fase 5)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.models import VinculoUsuario
from core.papeis import Papel
from governanca.models import RegistroBackup


@pytest.fixture
def cliente_plataforma(db):
    """Equipe da SafeStack com 2FA confirmado (obrigatorio para a plataforma)."""
    from django.utils import timezone

    from governanca.models import Dispositivo2FA

    equipe = get_user_model().objects.create_user(
        username="equipe.governanca",
        password="SenhaForteTeste123",
        email="equipe@safestack.com.br",
        is_staff=True,
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


@pytest.fixture
def cliente_recepcao(db, rede):
    usuario = get_user_model().objects.create_user(
        username="recepcao.governanca",
        password="SenhaForteTeste123",
        email="recepcao@academia.com.br",
    )
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.RECEPCAO, ativo=True)
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


def test_painel_do_cliente_tem_privacidade_dominio_e_seguranca(cliente_governanca):
    for rota, marca in (
        ("gestao:privacidade", "Pedidos de titulares"),
        ("gestao:dominio", "Endereço do seu painel"),
        ("gestao:seguranca", "duas etapas"),
    ):
        resposta = cliente_governanca.get(reverse(rota))
        assert resposta.status_code == 200, rota
        assert marca in resposta.content.decode(), rota


def test_recepcao_nao_acessa_privacidade_nem_dominio(cliente_recepcao):
    assert cliente_recepcao.get(reverse("gestao:privacidade")).status_code == 403
    assert cliente_recepcao.get(reverse("gestao:dominio")).status_code == 403


def test_verificacao_de_dominio_pelo_painel(cliente_governanca, rede, monkeypatch):
    import governanca.servicos as servicos

    monkeypatch.setattr(servicos, "_checar_txt", lambda dominio, valor: (False, "sem TXT"))
    monkeypatch.setattr(
        servicos, "_checar_arquivo_no_dominio", lambda dominio, valor: (True, "token encontrado")
    )
    resposta = cliente_governanca.post(
        reverse("gestao:dominio_verificar"), {"dominio": "academia.exemplo.com.br"}
    )
    assert resposta.status_code == 302
    rede.refresh_from_db()
    assert rede.dominio == "academia.exemplo.com.br"
    assert rede.dominio_status == "pronto"


def test_plataforma_telas_de_governanca(cliente_plataforma):
    for rota in (
        "plataforma:saude",
        "plataforma:backups",
        "plataforma:dominios",
        "plataforma:lgpd",
    ):
        assert cliente_plataforma.get(reverse(rota)).status_code == 200, rota


def test_plataforma_restrita(cliente_recepcao, client):
    assert cliente_recepcao.get(reverse("plataforma:saude")).status_code == 403
    assert client.get(reverse("plataforma:saude")).status_code == 302


def test_acao_de_backup_pela_tela(cliente_plataforma, settings, tmp_path):
    settings.BACKUP_DIR = tmp_path
    resposta = cliente_plataforma.post(reverse("plataforma:backups_acao"), {"acao": "executar"})
    assert resposta.status_code == 302
    registro = RegistroBackup.objects.order_by("-criado_em").first()
    assert registro is not None and registro.situacao == "ok"
    assert registro.verificado_em is not None


def test_exportar_cliente_pela_tela(cliente_plataforma, settings, tmp_path, rede):
    settings.BACKUP_DIR = tmp_path
    resposta = cliente_plataforma.post(
        reverse("plataforma:backups_acao"), {"acao": "exportar", "rede": rede.pk}
    )
    assert resposta.status_code == 302
    assert RegistroBackup.objects.filter(tipo=RegistroBackup.Tipo.TENANT, rede=rede).exists()


def test_verificar_dominio_pela_plataforma(cliente_plataforma, rede, monkeypatch):
    import governanca.servicos as servicos

    monkeypatch.setattr(servicos, "_checar_txt", lambda dominio, valor: (False, "sem TXT"))
    monkeypatch.setattr(
        servicos, "_checar_arquivo_no_dominio", lambda dominio, valor: (False, "nada")
    )
    resposta = cliente_plataforma.post(
        reverse("plataforma:dominios_acao", args=[rede.pk]), {"acao": "verificar"}
    )
    assert resposta.status_code == 302


def test_equipe_da_plataforma_sem_2fa_e_desviada_para_ativar(staff_sem_2fa):
    cliente, _usuario = staff_sem_2fa
    pagina = cliente.get(reverse("governanca:dois_fatores_cadastrar"))
    assert pagina.status_code == 200
    conteudo = pagina.content.decode().lower()
    assert "equipe da safestack" in conteudo or "segundo fator" in conteudo
