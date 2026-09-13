"""Limites e validadores de arquivo (video de aula, capa e foto) em um unico lugar.

Requisito de produto: video de atividade de ate **450 MB** e capa de ate **5 MB** nos formatos
**png, jpeg ou webp**. A regra mora aqui -- e nao no formulario -- porque ela precisa valer em tres
camadas: formulario, modelo e servico de envio em partes (quem usa a API nao passa pelo formulario).

Escolha de projeto sobre o conteudo do arquivo: a extensao mente, mas tentar adivinhar formatos
exoticos gera recusa injusta. Entao o validador confere a assinatura do arquivo e **rejeita quando
o conteudo claramente nao e o que o nome diz** (por exemplo: um PDF ou um executavel renomeado para
.png). Quando a assinatura e desconhecida, vale a extensao.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from django.core.exceptions import ValidationError

MB = 1024 * 1024
GB = 1024 * MB

TAMANHO_MAXIMO_DE_VIDEO = 450 * MB
TAMANHO_MAXIMO_DE_IMAGEM = 5 * MB

EXTENSOES_DE_VIDEO = ("mp4", "webm", "ogg", "mkv", "mov", "avi")
EXTENSOES_DE_IMAGEM = ("png", "jpg", "jpeg", "webp")

MIMES_DE_IMAGEM = ("image/png", "image/jpeg", "image/webp")
MIMES_DE_VIDEO = (
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/x-matroska",
    "video/quicktime",
    "video/x-msvideo",
)

#: Assinaturas conhecidas (magic bytes) que interessam para a conferencia de conteudo.
ASSINATURAS = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),
    (b"MZ", "application/x-msdownload"),
    (b"\x7fELF", "application/x-executable"),
    (b"\x1f\x8b", "application/gzip"),
    (b"OggS", "video/ogg"),
    (b"\x1a\x45\xdf\xa3", "video/x-matroska"),
    (b"\x00\x00\x01\xba", "video/mpeg"),
)


def tamanho_legivel(bytes_: int | None) -> str:
    """Tamanho em texto curto, para a mensagem de erro ficar clara para o usuario."""
    if not bytes_:
        return "0 B"
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidade == "GB":
            return f"{valor:.0f} {unidade}" if unidade == "B" else f"{valor:.1f} {unidade}"
        valor /= 1024
    return f"{valor:.1f} GB"


def extensao_de(nome: str) -> str:
    return (Path(nome or "").suffix or "").lstrip(".").lower()


def _cabecalho(origem, tamanho: int = 16) -> bytes:
    """Primeiros bytes do arquivo, sem consumir o stream do upload."""
    if origem is None:
        return b""
    if hasattr(origem, "read"):
        posicao = None
        with contextlib.suppress(AttributeError, OSError, ValueError):
            posicao = origem.tell()
        with contextlib.suppress(AttributeError, OSError, ValueError):
            dados = origem.read(tamanho) or b""
            if posicao is not None:
                origem.seek(posicao)
            return dados
        return b""
    caminho = Path(str(origem))
    if not caminho.is_file():
        return b""
    with caminho.open("rb") as arquivo:
        return arquivo.read(tamanho)


def tipo_real_do_arquivo(origem) -> str:
    """Tipo do arquivo pela assinatura do conteudo ('' quando a assinatura e desconhecida)."""
    cabecalho = _cabecalho(origem)
    if not cabecalho:
        return ""
    if cabecalho[4:8] == b"ftyp":
        return "video/mp4"
    if cabecalho.startswith(b"RIFF"):
        if cabecalho[8:12] == b"WEBP":
            return "image/webp"
        if cabecalho[8:12] == b"AVI ":
            return "video/x-msvideo"
        return "audio/wav"
    for assinatura, mime in ASSINATURAS:
        if cabecalho.startswith(assinatura):
            return mime
    return ""


def validar_tamanho(tamanho: int | None, *, limite: int, rotulo: str = "arquivo") -> None:
    if tamanho and tamanho > limite:
        raise ValidationError(
            f"O {rotulo} tem {tamanho_legivel(tamanho)} e o limite e {tamanho_legivel(limite)}."
        )


def validar_extensao(nome: str, *, aceitas: tuple[str, ...], rotulo: str = "arquivo") -> None:
    extensao = extensao_de(nome)
    if extensao and extensao not in aceitas:
        raise ValidationError(
            f"Formato de {rotulo} nao aceito ({extensao}). Use: {', '.join(aceitas)}."
        )


def validar_video_de_aula(arquivo) -> None:
    """Video de atividade: ate 450 MB, em mp4/webm/ogg/mkv/mov/avi."""
    validar_tamanho(getattr(arquivo, "size", None), limite=TAMANHO_MAXIMO_DE_VIDEO, rotulo="video")
    validar_extensao(getattr(arquivo, "name", ""), aceitas=EXTENSOES_DE_VIDEO, rotulo="video")
    tipo = tipo_real_do_arquivo(arquivo)
    if tipo and tipo not in MIMES_DE_VIDEO:
        raise ValidationError(
            f"O conteudo deste arquivo e {tipo}, que nao e um video aceito. "
            f"Envie mp4, webm, ogg, mkv, mov ou avi."
        )


def validar_imagem_de_capa(arquivo) -> None:
    """Capa e foto de perfil: ate 5 MB, em png/jpeg/webp de verdade (nao so no nome)."""
    validar_tamanho(getattr(arquivo, "size", None), limite=TAMANHO_MAXIMO_DE_IMAGEM, rotulo="capa")
    validar_extensao(getattr(arquivo, "name", ""), aceitas=EXTENSOES_DE_IMAGEM, rotulo="imagem")
    tipo = tipo_real_do_arquivo(arquivo)
    if tipo and tipo not in MIMES_DE_IMAGEM:
        raise ValidationError(
            f"O conteudo deste arquivo e {tipo}, que nao e uma imagem aceita. "
            f"Envie png, jpeg ou webp de verdade."
        )
