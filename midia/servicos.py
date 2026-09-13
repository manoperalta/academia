"""Servicos da midia: envio em partes, conclusao, processamento e entrega assinada.

O caminho no disco segue o isolamento por cliente da fase 5: ``media/redes/<slug>/...``. Nada de
arquivo solto na raiz de ``media/``, para um cliente nunca alcancar o arquivo do outro por acidente
de caminho.
"""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.db.models import Sum
from django.utils import timezone

from midia.models import TAMANHO_DA_PARTE, TAMANHO_MAXIMO, ArquivoDeMidia, ParteDeMidia, tamanho_legivel

SAL_DA_ENTREGA = "midia-entrega"
EXTENSOES = {
    "video": ".mp4",
    "imagem": ".jpg",
    "audio": ".m4a",
    "documento": ".pdf",
}


class ErroDeMidia(Exception):
    """Falha esperada no fluxo de midia (mensagem pronta para mostrar ao usuario)."""


# ------------------------------------------------------------------ caminhos
def raiz_da_midia() -> Path:
    return Path(settings.MEDIA_ROOT)


def pasta_do_cliente(rede) -> Path:
    return raiz_da_midia() / "redes" / rede.slug / "midia"


def pasta_temporaria(arquivo: ArquivoDeMidia) -> Path:
    return raiz_da_midia() / "redes" / arquivo.rede.slug / "tmp" / str(arquivo.pk)


def caminho_absoluto(arquivo: ArquivoDeMidia) -> Path:
    if not arquivo.caminho:
        raise ErroDeMidia("Este arquivo ainda nao tem conteudo gravado.")
    return raiz_da_midia() / arquivo.caminho


# ------------------------------------------------------------------ envio
def partes_esperadas(tamanho: int) -> int:
    if tamanho <= 0:
        return 0
    return (tamanho + TAMANHO_DA_PARTE - 1) // TAMANHO_DA_PARTE


def iniciar_envio(*, rede, titulo: str, nome_original: str, tamanho: int, tipo: str,
                  criado_por=None, unidade=None, aula=None, hash_esperado: str = "",
                  mime: str = "") -> ArquivoDeMidia:
    """Abre um envio e devolve o registro que recebera as partes."""
    if tipo not in dict(ArquivoDeMidia.Tipo.choices):
        raise ErroDeMidia("Tipo de arquivo nao suportado.")
    if tamanho <= 0:
        raise ErroDeMidia("Informe o tamanho do arquivo.")
    if tamanho > TAMANHO_MAXIMO:
        raise ErroDeMidia(
            f"Arquivo maior que o limite de {tamanho_legivel(TAMANHO_MAXIMO)}."
        )
    if not (titulo or "").strip():
        raise ErroDeMidia("Dê um titulo para o arquivo.")
    if not mime:
        mime = mimetypes.guess_type(nome_original or "")[0] or ""
    arquivo = ArquivoDeMidia.objects.create(
        rede=rede, unidade=unidade, aula=aula, titulo=titulo.strip(), nome_original=nome_original,
        tipo=tipo, mime=mime, tamanho_previsto=tamanho, hash_esperado=hash_esperado,
        criado_por=criado_por,
    )
    pasta_do_cliente(rede).mkdir(parents=True, exist_ok=True)
    pasta_temporaria(arquivo).mkdir(parents=True, exist_ok=True)
    return arquivo


def receber_parte(*, arquivo: ArquivoDeMidia, numero: int, conteudo: bytes,
                  hash_esperado: str = "") -> ParteDeMidia:
    """Grava uma parte no disco temporario, conferindo o hash. Reenvio da mesma parte e aceito."""
    if arquivo.situacao != ArquivoDeMidia.Situacao.ENVIANDO:
        raise ErroDeMidia("Este envio ja foi concluido ou cancelado.")
    total = arquivo.total_de_partes
    if numero < 1 or numero > total:
        raise ErroDeMidia(f"Parte fora da faixa: este arquivo tem {total} parte(s).")
    if not conteudo:
        raise ErroDeMidia("Parte vazia nao pode ser gravada.")

    resumo = hashlib.sha256(conteudo).hexdigest()
    if hash_esperado and hash_esperado.lower() != resumo:
        raise ErroDeMidia("A parte chegou corrompida: o hash nao confere. Reenvie esta parte.")

    pasta = pasta_temporaria(arquivo)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"parte-{numero:05d}"
    existente = arquivo.partes.filter(numero=numero).first()
    if existente is not None:
        if existente.hash_da_parte and existente.hash_da_parte != resumo:
            raise ErroDeMidia(
                "Esta parte ja foi recebida com outro conteudo. Recomece o envio."
            )
        return existente
    destino.write_bytes(conteudo)
    return ParteDeMidia.objects.create(
        arquivo=arquivo, numero=numero, tamanho_bytes=len(conteudo), hash_da_parte=resumo
    )


def partes_faltando(arquivo: ArquivoDeMidia) -> list[int]:
    recebidas = set(arquivo.partes.values_list("numero", flat=True))
    return [numero for numero in range(1, arquivo.total_de_partes + 1) if numero not in recebidas]


def concluir_envio(arquivo: ArquivoDeMidia) -> ArquivoDeMidia:
    """Junta as partes, confere tamanho e hash e passa o arquivo para processamento."""
    if arquivo.situacao != ArquivoDeMidia.Situacao.ENVIANDO:
        raise ErroDeMidia("Este envio ja foi concluido.")
    faltando = partes_faltando(arquivo)
    if faltando:
        raise ErroDeMidia(
            f"Ainda faltam {len(faltando)} parte(s) para concluir o envio."
        )

    extensao = Path(arquivo.nome_original or "").suffix or EXTENSOES.get(arquivo.tipo, ".bin")
    destino = pasta_do_cliente(arquivo.rede) / f"{uuid4().hex}{extensao}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    resumo = hashlib.sha256()
    gravado = 0
    with destino.open("wb") as saida:
        for parte in arquivo.partes.order_by("numero"):
            pedaco = (pasta_temporaria(arquivo) / f"parte-{parte.numero:05d}").read_bytes()
            resumo.update(pedaco)
            saida.write(pedaco)
            gravado += len(pedaco)

    if gravado != arquivo.tamanho_previsto:
        destino.unlink(missing_ok=True)
        _marcar_erro(arquivo, f"Tamanho final diferente do previsto ({gravado} de "
                              f"{arquivo.tamanho_previsto}).")
        raise ErroDeMidia("O arquivo montado nao bate com o tamanho previsto. Recomece o envio.")

    hash_final = resumo.hexdigest()
    if arquivo.hash_esperado and arquivo.hash_esperado.lower() != hash_final:
        destino.unlink(missing_ok=True)
        _marcar_erro(arquivo, "O hash do arquivo final nao confere com o do original.")
        raise ErroDeMidia("O arquivo chegou diferente do original (hash nao confere). Recomece.")

    arquivo.caminho = str(destino.relative_to(raiz_da_midia()))
    arquivo.tamanho_bytes = gravado
    arquivo.hash_final = hash_final
    arquivo.situacao = ArquivoDeMidia.Situacao.PROCESSANDO
    arquivo.concluido_em = timezone.now()
    arquivo.save(update_fields=["caminho", "tamanho_bytes", "hash_final", "situacao",
                               "concluido_em"])
    shutil.rmtree(pasta_temporaria(arquivo), ignore_errors=True)
    arquivo.partes.all().delete()
    arquivo = processar_midia(arquivo)
    if arquivo.aula_id:
        # o envio ja nasceu ligado a uma aula: ao concluir, ela passa a usar este arquivo
        arquivo = vincular_aula(arquivo, arquivo.aula, publicar=True)
    return arquivo


def _marcar_erro(arquivo: ArquivoDeMidia, mensagem: str) -> None:
    arquivo.situacao = ArquivoDeMidia.Situacao.ERRO
    arquivo.erro = mensagem[:300]
    arquivo.save(update_fields=["situacao", "erro"])


def processar_midia(arquivo: ArquivoDeMidia) -> ArquivoDeMidia:
    """Extrai o que der sem depender de binario externo (dimensoes de imagem, mimetype)."""
    caminho = caminho_absoluto(arquivo)
    if arquivo.tipo == ArquivoDeMidia.Tipo.IMAGEM:
        try:
            from PIL import Image

            with Image.open(caminho) as imagem:
                arquivo.largura, arquivo.altura = imagem.size
        except Exception as erro:  # pragma: no cover - depende do arquivo enviado
            arquivo.erro = f"Nao foi possivel ler a imagem: {erro}"[:300]
    elif arquivo.tipo == ArquivoDeMidia.Tipo.VIDEO:
        # Sem ffmpeg no ambiente: a duracao fica em branco de forma honesta, em vez de estimada.
        arquivo.duracao_segundos = None
    if not arquivo.mime:
        arquivo.mime = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    arquivo.situacao = ArquivoDeMidia.Situacao.PRONTO
    arquivo.processado_em = timezone.now()
    arquivo.save(update_fields=["largura", "altura", "duracao_segundos", "mime", "situacao",
                               "processado_em", "erro"])
    return arquivo


def vincular_aula(arquivo: ArquivoDeMidia, aula, publicar: bool = True) -> ArquivoDeMidia:
    """Liga a midia a uma aula: o campo de video da aula passa a apontar para o arquivo enviado."""
    if not arquivo.esta_pronto:
        raise ErroDeMidia("So entra na aula a midia que terminou de subir e processar.")
    arquivo.aula = aula
    arquivo.publicado = publicar
    arquivo.save(update_fields=["aula", "publicado"])
    if arquivo.tipo == ArquivoDeMidia.Tipo.VIDEO and hasattr(aula, "file_de_video"):
        aula.file_de_video.name = arquivo.caminho
        aula.save(update_fields=["file_de_video"])
    return arquivo


def remover_midia(arquivo: ArquivoDeMidia, apagar_arquivo: bool = False) -> ArquivoDeMidia:
    """Tira a midia do ar. O arquivo no disco so sai quando pedido explicitamente (LGPD)."""
    arquivo.situacao = ArquivoDeMidia.Situacao.REMOVIDO
    arquivo.publicado = False
    arquivo.save(update_fields=["situacao", "publicado"])
    if apagar_arquivo and arquivo.caminho:
        caminho_absoluto(arquivo).unlink(missing_ok=True)
    return arquivo


# ------------------------------------------------------------------ entrega
def url_de_entrega(arquivo: ArquivoDeMidia, minutos: int = 15) -> str:
    """URL assinada e temporaria: quem tiver o link entrega, quem nao tiver nao ve o arquivo."""
    from django.urls import reverse

    token = signing.dumps({"arquivo": arquivo.pk}, salt=SAL_DA_ENTREGA, compress=True)
    caminho = reverse("midia:entrega", args=[arquivo.pk])
    return f"{caminho}?t={token}&min={minutos}"


def arquivo_do_token(token: str, minutos: int = 15) -> ArquivoDeMidia:
    try:
        dados = signing.loads(token, salt=SAL_DA_ENTREGA, max_age=max(60, minutos * 60))
    except signing.SignatureExpired as erro:
        raise ErroDeMidia("Este link de midia expirou. Abra o video novamente.") from erro
    except signing.BadSignature as erro:
        raise ErroDeMidia("Link de midia invalido.") from erro
    arquivo = ArquivoDeMidia.objects.filter(pk=dados.get("arquivo")).first()
    if arquivo is None or arquivo.situacao != ArquivoDeMidia.Situacao.PRONTO:
        raise ErroDeMidia("Midia indisponivel.")
    return arquivo


def estatisticas(rede) -> dict:
    """Resumo para a tela: quanto ja subiu, quanto ainda esta subindo, quanto deu erro."""
    arquivos = ArquivoDeMidia.objects.filter(rede=rede).exclude(
        situacao=ArquivoDeMidia.Situacao.REMOVIDO
    )
    return {
        "total": arquivos.count(),
        "prontos": arquivos.filter(situacao=ArquivoDeMidia.Situacao.PRONTO).count(),
        "enviando": arquivos.filter(situacao=ArquivoDeMidia.Situacao.ENVIANDO).count(),
        "com_erro": arquivos.filter(situacao=ArquivoDeMidia.Situacao.ERRO).count(),
        "espaco": tamanho_legivel(
            arquivos.aggregate(total=Sum("tamanho_bytes"))["total"] or 0
        ),
    }
