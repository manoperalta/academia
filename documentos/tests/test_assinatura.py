"""Testes da assinatura eletronica com trilha verificavel."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from django.urls import reverse

from documentos import assinatura
from documentos.assinatura import ErroDeAssinatura
from documentos.models import Assinatura, EnvelopeDeAssinatura, Signatario

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_temporaria(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def test_envelope_guarda_o_hash_do_documento(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato 2026")
    assert envelope.hash_do_documento
    assert envelope.total_de_signatarios == 2  # aluno + representante da academia
    assert Path(envelope.caminho_do_documento).parts[0] == "redes"  # isolamento por cliente


def test_assinar_na_ordem_monta_a_corrente(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    primeiro = assinatura.proximo_signatario(envelope)
    segundo = envelope.signatarios.order_by("ordem", "pk")[1]

    with pytest.raises(ErroDeAssinatura):
        assinatura.assinar(signatario=segundo)  # fora de ordem

    assinatura.assinar(signatario=primeiro, ip="10.0.0.1")
    assinatura.assinar(signatario=segundo, ip="10.0.0.2")
    envelope.refresh_from_db()
    assert envelope.situacao == EnvelopeDeAssinatura.Situacao.ASSINADO
    assert envelope.concluido_em is not None

    assinaturas = list(
        Assinatura.objects.filter(signatario__envelope=envelope).order_by("criado_em")
    )
    assert assinaturas[0].hash_anterior == envelope.hash_do_documento
    assert assinaturas[1].hash_anterior == assinaturas[0].hash_da_assinatura
    assert assinaturas[0].endereco_ip == "10.0.0.1"


def test_assinatura_parcial_deixa_o_envelope_em_parcial(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    envelope.refresh_from_db()
    assert envelope.situacao == EnvelopeDeAssinatura.Situacao.PARCIAL


def test_assinar_duas_vezes_e_recusado(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    signatario = assinatura.proximo_signatario(envelope)
    assinatura.assinar(signatario=signatario)
    with pytest.raises(ErroDeAssinatura):
        assinatura.assinar(signatario=signatario)


def test_recusar_exige_motivo_e_marca_o_envelope(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    signatario = assinatura.proximo_signatario(envelope)
    with pytest.raises(ErroDeAssinatura):
        assinatura.recusar(signatario=signatario, motivo="")
    assinatura.recusar(signatario=signatario, motivo="nao concordo com a multa")
    envelope.refresh_from_db()
    signatario.refresh_from_db()
    assert envelope.situacao == EnvelopeDeAssinatura.Situacao.RECUSADO
    assert signatario.situacao == Signatario.Situacao.RECUSOU


def test_verificacao_aprova_a_corrente(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    conferencia = assinatura.verificar(envelope)
    assert conferencia["ok"] is True
    assert conferencia["divergencias"] == []
    assert conferencia["assinaturas"] == 1


def test_verificacao_pega_documento_trocado(rede, aluno, settings):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    caminho = Path(settings.MEDIA_ROOT) / envelope.caminho_do_documento
    caminho.write_bytes(b"%PDF-1.4 outro documento qualquer")
    conferencia = assinatura.verificar(envelope)
    assert conferencia["ok"] is False
    assert any("alterado" in divergencia for divergencia in conferencia["divergencias"])


def test_verificacao_pega_assinatura_adulterada(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    registro = Assinatura.objects.get()
    registro.hash_da_assinatura = hashlib.sha256(b"outra coisa").hexdigest()
    registro.save(update_fields=["hash_da_assinatura"])
    conferencia = assinatura.verificar(envelope)
    assert conferencia["ok"] is False
    assert any("nao confere" in divergencia for divergencia in conferencia["divergencias"])


def test_verificacao_pega_arquivo_ausente(rede, aluno, settings):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    (Path(settings.MEDIA_ROOT) / envelope.caminho_do_documento).unlink()
    conferencia = assinatura.verificar(envelope)
    assert conferencia["ok"] is False
    assert any("nao esta mais" in divergencia for divergencia in conferencia["divergencias"])


def test_termo_de_assinaturas_e_pdf_com_os_nomes(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato de teste")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    conteudo = assinatura.termo_de_assinaturas(envelope)
    assert conteudo.startswith(b"%PDF-1.4")
    assert b"Termo de assinaturas" in conteudo
    assert aluno.nome.encode("latin-1") in conteudo


def test_resumo_das_assinaturas(rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assinatura.assinar(signatario=assinatura.proximo_signatario(envelope))
    resumo = assinatura.resumo_das_assinaturas(rede)
    assert resumo["total"] == 1
    assert resumo["aguardando"] == 1
    assert resumo["pendentes_de_assinatura"] == 1


def test_telas_da_assinatura_abrem(cliente_painel, rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    assert cliente_painel.get(reverse("documentos:envelopes")).status_code == 200
    assert cliente_painel.get(reverse("documentos:envelope", args=[envelope.pk])).status_code == 200
    resposta = cliente_painel.get(reverse("documentos:termo_de_assinaturas", args=[envelope.pk]))
    assert resposta.status_code == 200 and resposta["Content-Type"] == "application/pdf"


def test_assinar_pela_tela(cliente_painel, rede, aluno):
    envelope = assinatura.criar_envelope(rede=rede, aluno=aluno, titulo="Contrato")
    signatario = assinatura.proximo_signatario(envelope)
    resposta = cliente_painel.post(reverse("documentos:assinar", args=[signatario.pk]))
    assert resposta.status_code == 302
    signatario.refresh_from_db()
    assert signatario.situacao == Signatario.Situacao.ASSINOU
    assert signatario.assinatura.hash_do_documento == envelope.hash_do_documento


def test_envelope_de_outra_rede_nao_abre(cliente_painel, outra_rede):
    from django.contrib.auth import get_user_model

    from core.models import Unidade
    from usuarios.models import Usuario

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    login = get_user_model().objects.create_user(username="alheio.assin", password="SenhaAlheia!23")
    alheio = Usuario.todos.create(
        rede=outra_rede, unidade=unidade_alheia, user=login, nome="Alheio", status_user="Ativo"
    )
    envelope = assinatura.criar_envelope(rede=outra_rede, aluno=alheio, titulo="Contrato alheio")
    assert cliente_painel.get(reverse("documentos:envelope", args=[envelope.pk])).status_code == 404
    assert (
        cliente_painel.get(
            reverse("documentos:termo_de_assinaturas", args=[envelope.pk])
        ).status_code
        == 404
    )
