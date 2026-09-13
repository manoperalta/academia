"""Testes dos documentos de negocio em PDF."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from documentos.pdf import DocumentoPDF, limpar_para_pdf, moeda, numero

pytestmark = pytest.mark.django_db


def texto_do_pdf(conteudo: bytes) -> str:
    """Textos legiveis de um PDF sem compressao (para conferir o conteudo de verdade)."""
    return conteudo.decode("latin-1", "replace")


# ------------------------------------------------------------------ gerador


def test_pdf_tem_cabecalho_catalogo_e_paginas():
    doc = DocumentoPDF(titulo="Documento de teste", subtitulo="Verificacao do gerador")
    doc.texto("Primeira linha")
    conteudo = doc.salvar()
    assert conteudo.startswith(b"%PDF-1.4")
    assert b"/Type /Catalog" in conteudo
    assert conteudo.count(b"/Type /Page ") == 1
    assert b"startxref" in conteudo
    assert b"Primeira linha" in conteudo


def test_pdf_multi_pagina_desenha_o_conteudo_da_segunda_pagina():
    """Regressao: a numeracao dos objetos ja colidiu e deixava a pagina 2 vazia."""
    doc = DocumentoPDF(titulo="Relatorio longo")
    for posicao in range(90):
        doc.texto(f"Linha de conteudo {posicao}")
    conteudo = doc.salvar()
    assert conteudo.count(b"/Type /Page ") == 2, "esperava duas paginas"
    trechos = conteudo.split(b" 0 obj" + bytes([10]) + b"<< /Length ")[1:]
    fluxos = [trecho.split(bytes([10]) + b"endstream")[0] for trecho in trechos]
    assert len(fluxos) == 2
    for fluxo in fluxos:
        assert len(fluxo) > 500, "fluxo de conteudo vazio em uma das paginas"
    primeira, segunda = fluxos
    assert b"Linha de conteudo 0" in primeira
    assert b"Linha de conteudo 89" in segunda
    assert b"Linha de conteudo 89" not in primeira


def test_xref_aponta_para_os_objetos_declarados():
    """Conferencia estrutural: cada deslocamento do xref cai em 'N 0 obj'."""
    doc = DocumentoPDF(titulo="Conferencia")
    for posicao in range(10):
        doc.texto(f"linha {posicao}")
    conteudo = doc.salvar()
    texto = texto_do_pdf(conteudo)
    declarado = int(texto.rsplit("/Size ", 1)[1].split(" ", 1)[0])
    linhas = [
        linha for linha in texto.split("\nxref\n", 1)[1].splitlines()[1:] if linha.endswith(" n ")
    ]
    assert len(linhas) == declarado - 1
    for indice, linha in enumerate(linhas, start=1):
        deslocamento = int(linha[:10])
        assert conteudo[deslocamento:].startswith(f"{indice} 0 obj".encode("latin-1"))


def test_moeda_e_numero_no_padrao_brasileiro():
    assert moeda("1234567.891") == "R$ 1.234.567,89"
    assert moeda("-9.95") == "-R$ 9,95"
    assert numero("8", 3) == "8,000"
    assert numero("1.5", 2) == "1,50"


def test_tipografia_que_nao_cabe_em_winansi_e_normalizada():
    assert limpar_para_pdf("Joao \u2014 Silva \u201creal\u201d \u2026") == 'Joao - Silva "real" ...'


# ------------------------------------------------------------------ documentos prontos


def test_acentos_sobrevivem_no_documento(aluno):
    from documentos import servicos

    conteudo = servicos.carteirinha_do_aluno(aluno.user)
    assert "Concei\u00e7\u00e3o".encode("latin-1") in conteudo


def test_comprovante_de_matricula(cliente_painel, aluno):
    resposta = cliente_painel.get(reverse("documentos:comprovante_de_matricula", args=[aluno.pk]))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert "comprovante-de-matricula" in resposta["Content-Disposition"]
    corpo = resposta.content
    assert corpo.startswith(b"%PDF")
    assert b"Comprovante de matricula" in corpo
    assert f"{aluno.user.pk:06d}".encode("latin-1") in corpo


def test_recibo_de_pagamento(cliente_painel, pagamento):
    resposta = cliente_painel.get(reverse("documentos:recibo", args=[pagamento.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content
    assert b"Recibo de pagamento" in corpo
    assert b"R$ 189,05" in corpo
    assert timezone.localdate().strftime("%d/%m/%Y").encode("latin-1") in corpo


def test_extrato_de_comissao_traz_a_memoria_linha_a_linha(cliente_painel, apuracao):
    resposta = cliente_painel.get(reverse("documentos:extrato_de_comissao", args=[apuracao.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content
    assert b"Extrato de comissao" in corpo
    assert b"Percentual do recebido na unidade" in corpo
    assert apuracao.hash_do_calculo[:16].encode("latin-1") in corpo


def test_contrato_de_adesao_tem_partes_e_minuta(cliente_painel, aluno):
    resposta = cliente_painel.get(reverse("documentos:contrato", args=[aluno.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content
    assert b"CONTRATADA" in corpo and b"CONTRATANTE" in corpo
    assert b"minuta" in corpo


def test_carteirinha_do_aluno_pelo_painel(cliente_painel, aluno):
    resposta = cliente_painel.get(reverse("documentos:carteirinha", args=[aluno.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content
    assert b"Carteirinha do aluno" in corpo
    assert b"Valida em qualquer unidade da rede" in corpo


def test_documento_de_outra_rede_nao_existe_para_quem_esta_logado(cliente_painel, outra_rede):
    from django.contrib.auth import get_user_model

    from core.models import Unidade
    from usuarios.models import Usuario

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    login = get_user_model().objects.create_user(username="alheio", password="SenhaAlheia!23")
    alheio = Usuario.todos.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        user=login,
        nome="Aluno de outra rede",
        status_user="Ativo",
    )
    resposta = cliente_painel.get(reverse("documentos:comprovante_de_matricula", args=[alheio.pk]))
    assert resposta.status_code == 404


def test_papel_sem_permissao_nao_baixa_documento_financeiro(cliente_restrito, pagamento):
    resposta = cliente_restrito.get(reverse("documentos:recibo", args=[pagamento.pk]))
    assert resposta.status_code == 403


def test_visitante_nao_baixa_nada(client, pagamento):
    resposta = client.get(reverse("documentos:recibo", args=[pagamento.pk]))
    assert resposta.status_code in (302, 403)


def test_aluno_baixa_a_propria_carteirinha_no_pwa(client, aluno):
    client.force_login(aluno.user)
    resposta = client.get(reverse("documentos:minha_carteirinha"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert b"Carteirinha do aluno" in resposta.content


def test_demonstrativo_de_repasse_traz_a_memoria_e_o_hash(cliente_painel, repasse):
    resposta = cliente_painel.get(reverse("documentos:demonstrativo_de_repasse", args=[repasse.pk]))
    assert resposta.status_code == 200
    corpo = resposta.content
    assert b"Demonstrativo de repasse" in corpo
    assert b"R$ 720,00" in corpo  # receita bruta do periodo
    assert b"R$ 18,00" in corpo  # exclusoes
    assert b"8,000" in corpo  # percentual do royalty
    assert b"R$ 56,16" in corpo  # royalty
    assert b"R$ 10,53" in corpo  # fundo de marketing
    assert b"R$ 66,69" in corpo  # total devido
    assert b"8934b0ee36f0be61a1f2cd98" in corpo  # hash para conferencia
    assert b"Piso minimo aplicado" not in corpo  # piso nao aplicado nao entra na memoria
