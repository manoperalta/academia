"""Capa da aula no painel: 5 MB nos formatos de imagem (requisito de produto).

O video da aula ja tinha teto e validacao; a capa tinha o limite no modelo, mas nao havia
campo na tela do painel -- por onde Admin da rede e Gestor da unidade cadastram a aula.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from aulas.models import Aulas, ImagemAula
from professores.models import Professor
from tests.apoio import criar

pytestmark = pytest.mark.django_db

LIMITE_DA_CAPA = 5 * 1024 * 1024


def _capa(formato: str = "PNG", nome: str = "capa.png", bytes_extras: int = 0):
    """Imagem real (o ImageField valida com o PIL, entao bytes falsos nao servem)."""
    buffer = BytesIO()
    Image.new("RGB", (80, 60), (12, 120, 90)).save(buffer, format=formato)
    conteudo = buffer.getvalue() + b"\x00" * bytes_extras
    return SimpleUploadedFile(nome, conteudo, content_type=f"image/{formato.lower()}")


@pytest.fixture
def professor_da_aula(db, rede, unidade, professor_user):
    return criar(Professor, rede=rede, unidade=unidade, user=professor_user, nome="Prof da Aula")


def _payload(professor, **extra):
    dados = {
        "nome": "Aula com capa",
        "descricao": "Aula de teste do painel",
        "professor": professor.user_id,
        "categorias_exercicios": "forca",
        "restricao": "nenhuma",
    }
    dados.update(extra)
    return dados


def test_admin_cadastra_aula_com_capa(cliente_logado, professor_da_aula):
    resposta = cliente_logado.post(
        reverse("gestao:aula_nova"), {**_payload(professor_da_aula), "capa": _capa()}
    )
    assert resposta.status_code == 302
    aula = Aulas.todos.get(nome="Aula com capa")
    assert aula.capa is not None, "a capa enviada precisa virar a capa da aula"
    assert str(aula.capa.imagem.name).endswith(".png")


def test_capa_aceita_jpeg(cliente_logado, professor_da_aula):
    resposta = cliente_logado.post(
        reverse("gestao:aula_nova"),
        {**_payload(professor_da_aula), "capa": _capa("JPEG", "capa.jpg")},
    )
    assert resposta.status_code == 302
    aula = Aulas.todos.get(nome="Aula com capa")
    assert str(aula.capa.imagem.name).endswith(".jpg")


def test_capa_maior_que_5_mb_e_recusada(cliente_logado, professor_da_aula):
    resposta = cliente_logado.post(
        reverse("gestao:aula_nova"),
        {**_payload(professor_da_aula), "capa": _capa(bytes_extras=LIMITE_DA_CAPA)},
    )
    assert resposta.status_code == 200, "o formulario volta com erro, nao salva"
    assert "capa" in resposta.context["form"].errors
    assert not Aulas.todos.filter(nome="Aula com capa").exists()


def test_arquivo_que_nao_e_imagem_e_recusado(cliente_logado, professor_da_aula):
    falso = SimpleUploadedFile(
        "capa.png", b"%PDF-1.4\n" + b"0" * 2_000, content_type="image/png"
    )
    resposta = cliente_logado.post(
        reverse("gestao:aula_nova"), {**_payload(professor_da_aula), "capa": falso}
    )
    assert resposta.status_code == 200
    assert "capa" in resposta.context["form"].errors
    assert not Aulas.todos.filter(nome="Aula com capa").exists()


def test_capa_e_opcional(cliente_logado, professor_da_aula):
    resposta = cliente_logado.post(reverse("gestao:aula_nova"), _payload(professor_da_aula))
    assert resposta.status_code == 302
    aula = Aulas.todos.get(nome="Aula com capa")
    assert aula.capa is None
    assert ImagemAula.todos.filter(aula=aula).count() == 0


def test_nova_capa_substitui_a_anterior(cliente_logado, professor_da_aula):
    cliente_logado.post(reverse("gestao:aula_nova"), {**_payload(professor_da_aula), "capa": _capa()})
    aula = Aulas.todos.get(nome="Aula com capa")
    primeira = aula.capa.imagem.name

    resposta = cliente_logado.post(
        reverse("gestao:aula_editar", args=[aula.pk]),
        {**_payload(professor_da_aula), "capa": _capa("JPEG", "capa-nova.jpg")},
    )
    assert resposta.status_code == 302
    aula.refresh_from_db()
    assert ImagemAula.todos.filter(aula=aula).count() == 1, "a capa do painel e uma so por aula"
    assert aula.capa.imagem.name != primeira
    assert str(aula.capa.imagem.name).endswith(".jpg")


def test_editar_sem_enviar_capa_mantem_a_atual(cliente_logado, professor_da_aula):
    cliente_logado.post(reverse("gestao:aula_nova"), {**_payload(professor_da_aula), "capa": _capa()})
    aula = Aulas.todos.get(nome="Aula com capa")
    anterior = aula.capa.imagem.name

    resposta = cliente_logado.post(
        reverse("gestao:aula_editar", args=[aula.pk]), _payload(professor_da_aula)
    )
    assert resposta.status_code == 302
    aula.refresh_from_db()
    assert aula.capa is not None
    assert aula.capa.imagem.name == anterior


def test_recepcao_nao_cadastra_aula_nem_capa(cliente_recepcao, professor_da_aula):
    resposta = cliente_recepcao.post(
        reverse("gestao:aula_nova"), {**_payload(professor_da_aula), "capa": _capa()}
    )
    assert resposta.status_code == 403
    assert not Aulas.todos.filter(nome="Aula com capa").exists()
