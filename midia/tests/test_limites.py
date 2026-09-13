"""Limites do envio de midia: video 450 MB, imagem 5 MB e cota de armazenamento do pacote."""

from __future__ import annotations

import hashlib

import pytest
from django.utils import timezone

from core.validadores import TAMANHO_MAXIMO_DE_IMAGEM, TAMANHO_MAXIMO_DE_VIDEO
from midia import servicos
from midia.models import TAMANHO_DA_PARTE, ArquivoDeMidia
from midia.servicos import ErroDeMidia

MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7" + b"\x00" * 24


def _abrir_e_enviar(*, rede, conteudo: bytes, tipo: str, nome: str):
    """Sobe um arquivo de verdade pelo servico em partes e conclui o envio."""
    arquivo = servicos.iniciar_envio(
        rede=rede,
        titulo="Teste",
        nome_original=nome,
        tamanho=len(conteudo),
        tipo=tipo,
        hash_esperado=hashlib.sha256(conteudo).hexdigest(),
    )
    for numero in range(1, arquivo.total_de_partes + 1):
        pedaco = conteudo[(numero - 1) * TAMANHO_DA_PARTE : numero * TAMANHO_DA_PARTE]
        servicos.receber_parte(arquivo=arquivo, numero=numero, conteudo=pedaco)
    return servicos.concluir_envio(arquivo)


def test_video_ate_450mb_e_aceito_na_abertura(db, rede):
    arquivo = servicos.iniciar_envio(
        rede=rede,
        titulo="Treino longo",
        nome_original="treino.mp4",
        tamanho=TAMANHO_MAXIMO_DE_VIDEO,
        tipo="video",
    )
    assert arquivo.limite_do_tipo("video") == TAMANHO_MAXIMO_DE_VIDEO
    assert arquivo.total_de_partes == -(-TAMANHO_MAXIMO_DE_VIDEO // TAMANHO_DA_PARTE)


def test_video_acima_de_450mb_e_recusado(db, rede):
    with pytest.raises(ErroDeMidia) as erro:
        servicos.iniciar_envio(
            rede=rede,
            titulo="Vídeo grande demais",
            nome_original="treino.mp4",
            tamanho=TAMANHO_MAXIMO_DE_VIDEO + 1,
            tipo="video",
        )
    assert "450.0 MB" in str(erro.value)


def test_capa_acima_de_5mb_e_recusada(db, rede):
    with pytest.raises(ErroDeMidia) as erro:
        servicos.iniciar_envio(
            rede=rede,
            titulo="Capa grande demais",
            nome_original="capa.png",
            tamanho=TAMANHO_MAXIMO_DE_IMAGEM + 1,
            tipo="imagem",
        )
    assert "5.0 MB" in str(erro.value)


def test_video_de_verdade_e_gravado_e_fica_pronto(db, rede):
    arquivo = _abrir_e_enviar(rede=rede, conteudo=MP4, tipo="video", nome="aula.mp4")
    assert arquivo.situacao == ArquivoDeMidia.Situacao.PRONTO
    assert arquivo.tamanho_bytes == len(MP4)
    assert arquivo.hash_final == hashlib.sha256(MP4).hexdigest()


def test_arquivo_de_pdf_enviado_como_video_e_recusado_no_fim(db, rede):
    """A extensao diz mp4; o conteudo e PDF. A recusa acontece ao juntar as partes."""
    with pytest.raises(ErroDeMidia) as erro:
        _abrir_e_enviar(rede=rede, conteudo=PDF, tipo="video", nome="aula.mp4")
    assert "application/pdf" in str(erro.value)
    arquivo = ArquivoDeMidia.objects.get(rede=rede)
    assert arquivo.situacao == ArquivoDeMidia.Situacao.ERRO


def test_executavel_enviado_como_capa_e_recusado(db, rede):
    with pytest.raises(ErroDeMidia):
        _abrir_e_enviar(
            rede=rede, conteudo=b"MZ\x90\x00" + b"\x00" * 24, tipo="imagem", nome="capa.png"
        )


# ------------------------------------------------------------------ cota do pacote
def _assinatura_com_cota(rede, gb: int):
    from plataforma.models import Assinatura, Pacote

    pacote = Pacote.objects.create(
        nome="Teste", codigo=f"teste-{gb}", limite_armazenamento_gb=gb, preco_mensal=0
    )
    return Assinatura.objects.create(
        rede=rede, pacote=pacote, renovacao_em=timezone.localdate()
    )


def test_sem_assinatura_nao_ha_cota(db, rede):
    from plataforma.servicos import espaco_disponivel, limite_de_armazenamento

    assert limite_de_armazenamento(rede) is None
    cabe, _ = espaco_disponivel(rede, bytes_novos=TAMANHO_MAXIMO_DE_VIDEO)
    assert cabe is True


def test_arquivo_que_nao_cabe_na_cota_do_pacote_e_recusado(db, rede, aula):
    _assinatura_com_cota(rede, 1)  # 1 GB
    ocupado = ArquivoDeMidia.objects.create(
        rede=rede,
        titulo="Video antigo",
        tipo="video",
        situacao=ArquivoDeMidia.Situacao.PRONTO,
        tamanho_previsto=1024**3,
        tamanho_bytes=1024**3,
    )
    from plataforma.servicos import uso_de_armazenamento

    assert uso_de_armazenamento(rede) == ocupado.tamanho_bytes

    with pytest.raises(ErroDeMidia) as erro:
        servicos.iniciar_envio(
            rede=rede,
            titulo="Mais um video",
            nome_original="outro.mp4",
            tamanho=1024**2,
            tipo="video",
        )
    assert "Espaco insuficiente" in str(erro.value)


def test_midia_removida_libera_espaco(db, rede):
    from plataforma.servicos import espaco_disponivel, uso_de_armazenamento

    _assinatura_com_cota(rede, 1)
    arquivo = ArquivoDeMidia.objects.create(
        rede=rede,
        titulo="Video removido",
        tipo="video",
        situacao=ArquivoDeMidia.Situacao.PRONTO,
        tamanho_previsto=1024**3,
        tamanho_bytes=1024**3,
    )
    arquivo.situacao = ArquivoDeMidia.Situacao.REMOVIDO
    arquivo.save(update_fields=["situacao"])
    assert uso_de_armazenamento(rede) == 0
    cabe, _ = espaco_disponivel(rede, bytes_novos=1024**2)
    assert cabe is True


def test_cota_da_rede_nao_vaza_para_outra_rede(db, rede, outra_rede):
    from plataforma.servicos import uso_de_armazenamento

    ArquivoDeMidia.objects.create(
        rede=outra_rede,
        titulo="Video da outra",
        tipo="video",
        situacao=ArquivoDeMidia.Situacao.PRONTO,
        tamanho_previsto=1024**3,
        tamanho_bytes=1024**3,
    )
    assert uso_de_armazenamento(rede) == 0
