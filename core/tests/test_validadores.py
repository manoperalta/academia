"""Limites de arquivo: video de aula 450 MB, capa/foto 5 MB e conferencia de conteudo."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from core.validadores import (
    TAMANHO_MAXIMO_DE_IMAGEM,
    TAMANHO_MAXIMO_DE_VIDEO,
    tamanho_legivel,
    tipo_real_do_arquivo,
    validar_imagem_de_capa,
    validar_video_de_aula,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
PDF = b"%PDF-1.7" + b"\x00" * 24
EXE = b"MZ\x90\x00" + b"\x00" * 24


class ArquivoFalso:
    """Upload de mentira: so o que os validadores precisam (nome, tamanho e primeiros bytes)."""

    def __init__(self, nome: str, conteudo: bytes = b"", tamanho: int | None = None):
        self.name = nome
        self._conteudo = conteudo
        self.size = tamanho if tamanho is not None else len(conteudo)
        self._posicao = 0

    def read(self, quantidade: int = -1) -> bytes:
        if quantidade is None or quantidade < 0:
            return self._conteudo
        return self._conteudo[:quantidade]

    def tell(self) -> int:
        return self._posicao

    def seek(self, posicao: int) -> int:
        self._posicao = posicao
        return posicao


# ------------------------------------------------------------------ conteudo real
@pytest.mark.parametrize(
    ("conteudo", "esperado"),
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (WEBP, "image/webp"),
        (MP4, "video/mp4"),
        (PDF, "application/pdf"),
        (EXE, "application/x-msdownload"),
        (b"lixo qualquer", ""),
    ],
)
def test_tipo_real_do_arquivo_pela_assinatura(conteudo, esperado):
    assert tipo_real_do_arquivo(ArquivoFalso("arquivo", conteudo)) == esperado


def test_tipo_real_le_arquivo_do_disco(tmp_path):
    caminho = tmp_path / "capa.png"
    caminho.write_bytes(PNG)
    assert tipo_real_do_arquivo(caminho) == "image/png"


def test_tamanho_legivel():
    assert tamanho_legivel(0) == "0 B"
    assert tamanho_legivel(5 * 1024 * 1024) == "5.0 MB"
    assert tamanho_legivel(450 * 1024 * 1024) == "450.0 MB"


# ------------------------------------------------------------------ video de aula
def test_video_no_limite_e_aceito():
    validar_video_de_aula(ArquivoFalso("treino.mp4", MP4, tamanho=TAMANHO_MAXIMO_DE_VIDEO))


def test_video_acima_de_450mb_e_recusado():
    with pytest.raises(ValidationError) as erro:
        validar_video_de_aula(
            ArquivoFalso("treino.mp4", MP4, tamanho=TAMANHO_MAXIMO_DE_VIDEO + 1)
        )
    assert "450.0 MB" in str(erro.value)


def test_video_com_extensao_estranha_e_recusado():
    with pytest.raises(ValidationError) as erro:
        validar_video_de_aula(ArquivoFalso("treino.exe", MP4))
    assert "nao aceito" in str(erro.value)


def test_arquivo_que_nao_e_video_com_nome_de_video_e_recusado():
    with pytest.raises(ValidationError) as erro:
        validar_video_de_aula(ArquivoFalso("treino.mp4", PDF))
    assert "application/pdf" in str(erro.value)


# ------------------------------------------------------------------ capa e foto
def test_capa_no_limite_e_aceita():
    validar_imagem_de_capa(ArquivoFalso("capa.png", PNG, tamanho=TAMANHO_MAXIMO_DE_IMAGEM))


def test_capa_acima_de_5mb_e_recusada():
    with pytest.raises(ValidationError) as erro:
        validar_imagem_de_capa(
            ArquivoFalso("capa.png", PNG, tamanho=TAMANHO_MAXIMO_DE_IMAGEM + 1)
        )
    assert "5.0 MB" in str(erro.value)


def test_capa_em_formato_nao_aceito_e_recusada():
    with pytest.raises(ValidationError) as erro:
        validar_imagem_de_capa(ArquivoFalso("foto.gif", b"GIF89a" + b"\x00" * 16))
    assert "nao aceito" in str(erro.value)


def test_executavel_renomeado_para_png_e_recusado():
    """O nome diz png, o conteudo e programa: recusa (requisito: so foto de verdade)."""
    with pytest.raises(ValidationError) as erro:
        validar_imagem_de_capa(ArquivoFalso("foto.png", EXE))
    assert "application/x-msdownload" in str(erro.value)


def test_pdf_renomeado_para_webp_e_recusado():
    with pytest.raises(ValidationError):
        validar_imagem_de_capa(ArquivoFalso("capa.webp", PDF))
