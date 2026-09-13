"""O ponto de compra no cadastro publico respeita o interruptor da plataforma."""

from __future__ import annotations

import pytest
from django.urls import reverse

from plataforma.models import ConfiguracaoPlataforma
from vitrine.forms import CadastroPublicoForm

pytestmark = pytest.mark.django_db


def _ligar_compra():
    configuracao = ConfiguracaoPlataforma.obter()
    configuracao.permitir_compra_de_pacote = True
    configuracao.save(update_fields=["permitir_compra_de_pacote"])


def test_formulario_oferece_apenas_teste_com_a_compra_desligada(pacotes_publicos):
    form = CadastroPublicoForm(pacote=pacotes_publicos["ouro"])
    assert [codigo for codigo, _ in form.fields["modalidade"].choices] == ["trial"]
    assert form.compra_liberada is False
    assert "desabilitada" in form.fields["modalidade"].help_text


def test_formulario_oferece_assinatura_com_a_compra_ligada(pacotes_publicos):
    _ligar_compra()
    form = CadastroPublicoForm(pacote=pacotes_publicos["ouro"])
    assert [codigo for codigo, _ in form.fields["modalidade"].choices] == ["trial", "pagamento"]
    assert form.compra_liberada is True


def test_pagina_de_cadastro_avisa_que_a_compra_esta_desligada(client, pacotes_publicos):
    resposta = client.get(reverse("vitrine:cadastro"), {"plano": "ouro"})
    assert resposta.status_code == 200
    assert resposta.context["compra_liberada"] is False


def test_paginas_publicas_expoem_o_estado_da_compra(client, pacotes_publicos):
    for nome in ("vitrine:home", "vitrine:planos", "vitrine:cadastro"):
        resposta = client.get(reverse(nome))
        assert resposta.status_code == 200
        assert resposta.context["compra_liberada"] is False


def test_cadastro_com_pagamento_pela_web_e_recusado_quando_desligado(
    client, pacotes_publicos, dados_cadastro
):
    dados = {**dados_cadastro, "pacote": "ouro", "modalidade": "pagamento"}
    resposta = client.post(reverse("vitrine:cadastro") + "?plano=ouro", dados)
    assert resposta.status_code == 200
    assert not resposta.context["compra_liberada"]
    from core.models import Rede

    assert not Rede.todos.filter(slug=dados["slug"]).exists()
