"""Backup, verificacao por restauracao de teste e retencao (RNF-005)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils import timezone

from governanca.models import RegistroBackup
from governanca.servicos import (
    DIAS_DE_RETENCAO,
    aplicar_retencao_de_backups,
    executar_backup,
    exportar_tenant,
    verificar_backup,
)


@pytest.fixture
def pasta_de_backup(settings, tmp_path):
    settings.BACKUP_DIR = tmp_path
    return tmp_path


def test_backup_logico_grava_arquivo_hash_e_retencao(db, pasta_de_backup):
    registro = executar_backup(metodo="json")
    arquivo = Path(registro.arquivo)
    assert registro.situacao == RegistroBackup.Situacao.OK
    assert arquivo.exists() and arquivo.stat().st_size > 0
    assert len(registro.sha256) == 64
    assert registro.retencao_ate == timezone.now().date() + timedelta(days=DIAS_DE_RETENCAO)


def test_verificacao_por_restauracao_marca_como_verificado(db, pasta_de_backup):
    registro = executar_backup(metodo="json")
    verificacao = verificar_backup(registro)
    registro.refresh_from_db()
    assert verificacao["ok"] is True
    assert registro.verificado_em is not None
    assert "registros" in registro.verificacao


def test_verificacao_detecta_arquivo_alterado(db, pasta_de_backup):
    registro = executar_backup(metodo="json")
    Path(registro.arquivo).write_bytes(b"[]")
    verificacao = verificar_backup(registro)
    assert verificacao["ok"] is False
    assert "hash" in verificacao["detalhe"]


def test_verificacao_sem_backup(db):
    assert verificar_backup()["ok"] is False


def test_exportacao_de_um_cliente(db, pasta_de_backup, rede, aluno_com_login):
    registro = exportar_tenant(rede)
    assert registro.situacao == RegistroBackup.Situacao.OK
    assert registro.rede == rede
    dados = json.loads(Path(registro.arquivo).read_text(encoding="utf-8"))
    assert dados["rede"]["slug"] == rede.slug
    assert "usuarios.usuario" in dados["tabelas"]
    assert len(dados["tabelas"]["usuarios.usuario"]) == 1
    assert verificar_backup(registro)["ok"] is True


def test_retencao_simulada_nao_apaga(db, pasta_de_backup):
    antigos = []
    for dias in (1, 2, 3, 40, 41, 42, 100, 101, 102, 103, 104):
        caminho = pasta_de_backup / f"antigo-{dias}.json"
        caminho.write_text("[]")
        registro = RegistroBackup.objects.create(
            arquivo=str(caminho), tamanho_bytes=2, situacao=RegistroBackup.Situacao.OK
        )
        RegistroBackup.objects.filter(pk=registro.pk).update(
            criado_em=timezone.now() - timedelta(days=dias)
        )
        antigos.append(registro)
    resultado = aplicar_retencao_de_backups(dry_run=True)
    assert resultado["dry_run"] is True
    assert resultado["apagados"] == 0
    assert RegistroBackup.objects.count() == len(antigos)
    assert resultado["detalhes"]


def test_alertas_de_backup(db, pasta_de_backup):
    from governanca.servicos import alertas_pendentes

    assert any("nenhum backup" in alerta for alerta in alertas_pendentes())
    executar_backup(metodo="json")
    alertas = alertas_pendentes()
    assert any("nao foi verificado" in alerta for alerta in alertas)
    registro = RegistroBackup.objects.order_by("-criado_em").first()
    verificar_backup(registro)
    assert not any("nao foi verificado" in alerta for alerta in alertas_pendentes())


def test_comando_de_backup(db, pasta_de_backup, capsys):
    call_command("backup_banco", "--metodo", "json")
    saida = capsys.readouterr().out
    assert "Backup ok" in saida and "Verificacao" in saida and "Retencao" in saida
