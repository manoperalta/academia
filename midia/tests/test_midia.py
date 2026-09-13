"""Testes do envio em partes, do processamento e da entrega assinada."""

from __future__ import annotations

import hashlib
import io
import time

import pytest
from django.core import signing
from django.urls import reverse

from midia import servicos
from midia.models import ArquivoDeMidia
from midia.servicos import SAL_DA_ENTREGA

pytestmark = pytest.mark.django_db


def sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def abrir_envio(cliente, conteudo: bytes, **extra):
    dados = {
        "titulo": "Video de teste",
        "nome": "video.mp4",
        "tamanho": len(conteudo),
        "tipo": "video",
        "mime": "video/mp4",
        "hash": sha(conteudo),
    }
    dados.update(extra)
    return cliente.post(reverse("midia:api_iniciar"), data=dados, content_type="application/json")


def mandar_parte(cliente, arquivo_id: int, numero: int, conteudo: bytes, hash_: str | None = None):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return cliente.post(
        reverse("midia:api_parte", args=[arquivo_id]),
        data={
            "numero": numero,
            "hash": hash_ if hash_ is not None else sha(conteudo),
            "parte": SimpleUploadedFile(f"parte{numero}", conteudo),
        },
    )


def enviar_tudo(cliente, conteudo: bytes, **extra) -> tuple[int, object]:
    inicio = abrir_envio(cliente, conteudo, **extra).json()
    tamanho = inicio["tamanho_da_parte"]
    for numero in range(1, inicio["total_de_partes"] + 1):
        pedaco = conteudo[(numero - 1) * tamanho : numero * tamanho]
        resposta = mandar_parte(cliente, inicio["id"], numero, pedaco)
        assert resposta.status_code == 200, resposta.content
    fim = cliente.post(reverse("midia:api_concluir", args=[inicio["id"]]))
    return inicio["id"], fim


# ------------------------------------------------------------------ caminho feliz


def test_envio_completo_grava_confere_e_libera_o_player(cliente_painel):
    conteudo = b"a" * (servicos.TAMANHO_DA_PARTE * 2 + 1234)  # tres partes: duas cheias e uma curta
    arquivo_id, fim = enviar_tudo(cliente_painel, conteudo, titulo="Aula completa")
    assert fim.status_code == 200, fim.content
    dados = fim.json()
    assert dados["situacao"] == "pronto"
    assert dados["tamanho"] == len(conteudo)
    assert dados["hash"] == sha(conteudo)  # hash do arquivo montado bate com o do original

    arquivo = ArquivoDeMidia.objects.get(pk=arquivo_id)
    assert arquivo.partes.count() == 0, "as partes saem do disco depois de montar"
    assert servicos.caminho_absoluto(arquivo).read_bytes() == conteudo
    assert "redes/academia-midia/midia/" in arquivo.caminho  # isolamento por cliente

    player = cliente_painel.get(reverse("midia:player", args=[arquivo_id]))
    assert player.status_code == 200
    entrega = cliente_painel.get(servicos.url_de_entrega(arquivo))
    assert entrega.status_code == 200
    assert entrega["Content-Type"].startswith("video/")


def test_reenviar_a_mesma_parte_e_aceito(cliente_painel):
    conteudo = b"b" * 1000
    inicio = abrir_envio(cliente_painel, conteudo).json()
    primeira = mandar_parte(cliente_painel, inicio["id"], 1, conteudo)
    segunda = mandar_parte(cliente_painel, inicio["id"], 1, conteudo)
    assert primeira.status_code == 200 and segunda.status_code == 200
    assert segunda.json()["recebidas"] == 1, "nao duplica a parte"


def test_parte_corrompida_e_recusada_com_mensagem(cliente_painel):
    conteudo = b"c" * 1000
    inicio = abrir_envio(cliente_painel, conteudo).json()
    resposta = mandar_parte(cliente_painel, inicio["id"], 1, conteudo, hash_="0" * 64)
    assert resposta.status_code == 400
    assert "corrompida" in resposta.json()["erro"]


def test_parte_fora_da_faixa_e_recusada(cliente_painel):
    conteudo = b"d" * 1000
    inicio = abrir_envio(cliente_painel, conteudo).json()
    resposta = mandar_parte(cliente_painel, inicio["id"], 7, conteudo)
    assert resposta.status_code == 400
    assert "fora da faixa" in resposta.json()["erro"]


def test_concluir_sem_todas_as_partes_avisa_quanto_falta(cliente_painel):
    conteudo = b"e" * (servicos.TAMANHO_DA_PARTE * 2 + 10)
    inicio = abrir_envio(cliente_painel, conteudo).json()
    mandar_parte(cliente_painel, inicio["id"], 1, conteudo[: servicos.TAMANHO_DA_PARTE])
    resposta = cliente_painel.post(reverse("midia:api_concluir", args=[inicio["id"]]))
    assert resposta.status_code == 400
    assert "faltam 2 parte" in resposta.json()["erro"]


def test_tamanho_diferente_do_previsto_marca_erro(cliente_painel):
    conteudo = b"f" * 1000
    inicio = abrir_envio(cliente_painel, conteudo, tamanho=5000).json()  # mente no tamanho
    mandar_parte(cliente_painel, inicio["id"], 1, conteudo)
    resposta = cliente_painel.post(reverse("midia:api_concluir", args=[inicio["id"]]))
    assert resposta.status_code == 400
    arquivo = ArquivoDeMidia.objects.get(pk=inicio["id"])
    assert arquivo.situacao == ArquivoDeMidia.Situacao.ERRO
    assert "Tamanho final" in arquivo.erro


def test_hash_final_diferente_do_original_marca_erro(cliente_painel):
    conteudo = b"g" * 1000
    inicio = abrir_envio(cliente_painel, conteudo).json()
    ArquivoDeMidia.objects.filter(pk=inicio["id"]).update(hash_esperado="1" * 64)
    mandar_parte(cliente_painel, inicio["id"], 1, conteudo)
    resposta = cliente_painel.post(reverse("midia:api_concluir", args=[inicio["id"]]))
    assert resposta.status_code == 400
    arquivo = ArquivoDeMidia.objects.get(pk=inicio["id"])
    assert arquivo.situacao == ArquivoDeMidia.Situacao.ERRO
    assert "hash" in arquivo.erro.lower()


# ------------------------------------------------------------------ entrega assinada


def test_token_adulterado_nao_entrega(cliente_painel):
    conteudo = b"h" * 500
    arquivo_id, _ = enviar_tudo(cliente_painel, conteudo)
    resposta = cliente_painel.get(
        reverse("midia:entrega", args=[arquivo_id]), {"t": "assinatura-falsa", "min": 15}
    )
    assert resposta.status_code == 403


def test_token_expirado_nao_entrega(cliente_painel, monkeypatch):
    """Adianta o relogio do modulo de assinatura: o token nasce valido e vence na consulta."""
    conteudo = b"i" * 500
    arquivo_id, _ = enviar_tudo(cliente_painel, conteudo)
    token = signing.dumps({"arquivo": arquivo_id}, salt=SAL_DA_ENTREGA, compress=True)
    relogio_real = time.time  # guardar a funcao antes de trocar o atributo do modulo
    monkeypatch.setattr("django.core.signing.time.time", lambda: relogio_real() + 4000)
    resposta = cliente_painel.get(
        reverse("midia:entrega", args=[arquivo_id]), {"t": token, "min": 15}
    )
    assert resposta.status_code == 403
    assert "expirou" in resposta.json()["erro"]


def test_token_de_um_arquivo_nao_serve_para_outro(cliente_painel):
    conteudo = b"j" * 500
    primeiro_id, _ = enviar_tudo(cliente_painel, conteudo, titulo="Primeiro")
    segundo_id, _ = enviar_tudo(cliente_painel, conteudo, titulo="Segundo")
    token = signing.dumps({"arquivo": primeiro_id}, salt=SAL_DA_ENTREGA, compress=True)
    resposta = cliente_painel.get(
        reverse("midia:entrega", args=[segundo_id]), {"t": token, "min": 15}
    )
    assert resposta.status_code == 403
    assert "nao corresponde" in resposta.json()["erro"]


# ------------------------------------------------------------------ imagem, aula e isolamento


def test_imagem_ganha_dimensoes_no_processamento(cliente_painel):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 120, 200)).save(buffer, "PNG")
    conteudo = buffer.getvalue()
    arquivo_id, fim = enviar_tudo(
        cliente_painel, conteudo, tipo="imagem", nome="foto.png", mime="image/png"
    )
    assert fim.json()["situacao"] == "pronto"
    arquivo = ArquivoDeMidia.objects.get(pk=arquivo_id)
    assert (arquivo.largura, arquivo.altura) == (64, 48)


def test_midia_vinculada_a_aula_alimenta_o_campo_de_video(cliente_painel, aula):
    conteudo = b"k" * 800
    arquivo_id, _ = enviar_tudo(cliente_painel, conteudo, aula=aula.pk)
    aula.refresh_from_db()
    arquivo = ArquivoDeMidia.objects.get(pk=arquivo_id)
    assert arquivo.aula_id == aula.pk
    assert arquivo.publicado is True
    assert aula.file_de_video.name == arquivo.caminho


def test_aluno_assiste_a_midia_publicada_da_propria_rede(client, aluno, cliente_painel, aula):
    conteudo = b"l" * 800
    arquivo_id, _ = enviar_tudo(cliente_painel, conteudo, aula=aula.pk)
    client.force_login(aluno.user)
    resposta = client.get(reverse("midia:aluno_assistir", args=[arquivo_id]))
    assert resposta.status_code == 302
    assert "t=" in resposta["Location"]


def test_midia_de_outra_rede_nao_aparece_nem_entrega(cliente_painel, outra_rede):
    from core.models import Unidade as UnidadeModelo

    unidade_alheia = UnidadeModelo.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    alheio = servicos.iniciar_envio(
        rede=outra_rede,
        titulo="Da outra rede",
        nome_original="x.mp4",
        tamanho=100,
        tipo="video",
        unidade=unidade_alheia,
    )
    assert cliente_painel.get(reverse("midia:player", args=[alheio.pk])).status_code == 404
    assert cliente_painel.get(reverse("midia:api_status", args=[alheio.pk])).status_code == 404
    assert cliente_painel.post(reverse("midia:api_concluir", args=[alheio.pk])).status_code == 404


def test_aluno_nao_entra_na_midia_do_painel(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("midia:lista")).status_code == 403


def test_visitante_vai_para_o_login(client):
    resposta = client.get(reverse("midia:lista"))
    assert resposta.status_code in (302, 403)


def test_estatisticas_da_rede(cliente_painel):
    enviar_tudo(cliente_painel, b"m" * 400, titulo="Um")
    enviar_tudo(cliente_painel, b"n" * 400, titulo="Dois")
    resumo = servicos.estatisticas(ArquivoDeMidia.objects.first().rede)
    assert resumo["total"] == 2 and resumo["prontos"] == 2 and resumo["com_erro"] == 0
    assert resumo["espaco"].endswith(("B", "KB", "MB"))


def test_iniciar_envio_recusa_arquivo_grande_demais(cliente_painel):
    resposta = cliente_painel.post(
        reverse("midia:api_iniciar"),
        data={
            "titulo": "Gigante",
            "nome": "g.mp4",
            "tamanho": servicos.TAMANHO_MAXIMO + 1,
            "tipo": "video",
        },
        content_type="application/json",
    )
    assert resposta.status_code == 400
    assert "limite" in resposta.json()["erro"]


def test_iniciar_envio_recusa_tipo_desconhecido(cliente_painel):
    resposta = cliente_painel.post(
        reverse("midia:api_iniciar"),
        data={"titulo": "Executavel", "nome": "x.exe", "tamanho": 100, "tipo": "programa"},
        content_type="application/json",
    )
    assert resposta.status_code == 400
