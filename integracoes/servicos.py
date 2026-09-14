"""Regras da tela de integracoes: ler, gravar, mascarar, espelhar e testar.

Um provedor de terceiro entrega valores (chave da API, token, usuario, certificado). Este
servico e o unico lugar que escreve esses valores, para que a tela nunca grave um segredo
errado e para que os modelos antigos (gateway, fiscal, notificacoes) continuem alimentados.
"""

from __future__ import annotations

import secrets
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from integracoes import catalogo
from integracoes.models import IntegracaoDaRede

#: Marcador do que esta gravado sem revelar o segredo.
MASCARA = "********"


def mascarar(valor) -> str:
    """Mostra que existe um valor, guardando as 4 ultimas posicoes quando fizer sentido."""
    texto = str(valor or "")
    if not texto:
        return ""
    if len(texto) <= 4:
        return MASCARA
    return f"{MASCARA}{texto[-4:]}"


def token_sugerido() -> str:
    """Token do equipamento (catraca): o mesmo valor precisa ser gravado no leitor."""
    return secrets.token_urlsafe(24)


def _registro(rede, chave: str) -> IntegracaoDaRede | None:
    if rede is None:
        return None
    return IntegracaoDaRede.todos.filter(rede=rede, provedor=chave).first()


def valores_reais(rede, chave: str) -> dict:
    """Valores gravados (com segredo). Uso interno: cobranca, fiscal, notificacoes."""
    registro = _registro(rede, chave)
    return dict(registro.campos) if registro else {}


def valores_para_a_tela(rede, chave: str) -> dict:
    """Valores para exibir: segredo sai mascarado, nunca em texto."""
    valores = valores_reais(rede, chave)
    return {
        nome: (mascarar(valor) if nome in catalogo.campos_sensiveis(chave) else valor)
        for nome, valor in valores.items()
    }


def _faltando_em(valores: dict, chave: str) -> list[str]:
    """Rotulos dos campos obrigatorios vazios dentro de um conjunto de valores."""
    return [
        campo.rotulo
        for campo in catalogo.campos_obrigatorios(chave)
        if not str(valores.get(campo.nome, "")).strip()
    ]


def faltando(rede, chave: str) -> list[str]:
    """Rotulos dos campos obrigatorios que ainda estao vazios (estado gravado)."""
    return _faltando_em(valores_reais(rede, chave), chave)


def esta_configurada(rede, chave: str) -> bool:
    return not faltando(rede, chave)


def salvar(rede, chave: str, dados: dict, *, usuario=None, espelhar: bool = True) -> IntegracaoDaRede:
    """Grava os valores do provedor.

    Campo de segredo em branco mantem o valor atual (o operador so redigita quando troca);
    os demais campos vazios apagam o valor, que e o comportamento esperado na tela.
    """
    integracao = catalogo.obter(chave)
    if integracao is None:
        raise ValueError(f"Provedor desconhecido: {chave}")

    registro, _ = IntegracaoDaRede.todos.get_or_create(rede=rede, provedor=chave)
    valores = dict(registro.campos or {})
    for campo in integracao.campos:
        if campo.nome not in dados:
            continue
        valor = dados.get(campo.nome)
        if campo.sensivel:
            if valor in (None, ""):
                continue  # mantem o segredo atual
            valores[campo.nome] = str(valor)
        elif campo.tipo == catalogo.BOOLEANO:
            valores[campo.nome] = bool(valor)
        elif campo.de_arquivo:
            if valor:
                registro.arquivo = valor
                valores[campo.nome] = getattr(valor, "name", str(valor))
        elif valor in (None, ""):
            valores.pop(campo.nome, None)
        else:
            valores[campo.nome] = str(valor)

    registro.campos = valores
    #: O estado "ativa" vem do que acabou de ser gravado (nao do banco, que ainda tem o valor antigo).
    registro.ativo = not _faltando_em(valores, chave) if rede is not None else False
    registro.atualizada_por = usuario
    registro.atualizada_em = timezone.now()
    registro.save()
    if espelhar:
        sincronizar(registro)
    return registro


def panorama(rede) -> list[dict]:
    """Estado de cada provedor para a lista da tela (o que falta, se esta ativa)."""
    itens = []
    for integracao in catalogo.CATALOGO.values():
        registro = _registro(rede, integracao.chave)
        pendentes = faltando(rede, integracao.chave)
        itens.append(
            {
                "chave": integracao.chave,
                "nome": integracao.nome,
                "categoria": integracao.categoria,
                "resumo": integracao.resumo,
                "situacao_atual": integracao.situacao_atual,
                "configurada": not pendentes,
                "ativa": bool(registro.ativo) if registro else False,
                "faltando": pendentes,
                "atualizada_em": registro.atualizada_em if registro else None,
                "valores": valores_para_a_tela(rede, integracao.chave),
                "registro": registro,
            }
        )
    return itens


def testar(rede, chave: str) -> tuple[bool, str]:
    """Diz o que da para afirmar sobre a integracao agora (sem inventar conexao).

    Nenhum provedor aqui autoriza chamada de teste sem credencial real: quando falta valor
    a resposta e o que falta; quando esta completo, a resposta diz que os valores estao
    gravados e que o teste real acontece no fluxo do provedor (webhook, emissao, envio).
    """
    integracao = catalogo.obter(chave)
    if integracao is None:
        return False, "Provedor desconhecido."
    pendentes = faltando(rede, chave)
    if pendentes:
        return False, "Falta preencher: " + ", ".join(pendentes) + "."
    return True, (
        "Valores completos e gravados. O teste real acontece no fluxo do provedor "
        "(webhook de baixa, emissao da nota, envio da mensagem)."
    )


# ------------------------------------------------------------------ espelho
def _decimal(valor) -> Decimal | None:
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


def sincronizar(registro: IntegracaoDaRede) -> list[str]:
    """Espelha os valores nos modelos antigos, para nao existir duas verdades.

    Vale para os provedores que ja tem modelo no sistema (gateway de pagamento, configuracao
    fiscal, e-mail e WhatsApp): quem consome aqueles modelos passa a ver o que foi cadastrado
    na tela de integracoes. Os demais provedores ficam so no registro da integracao.
    """
    rede = registro.rede
    if rede is None:
        return []
    valores = dict(registro.campos or {})
    espelhados: list[str] = []

    if registro.provedor == "asaas" and valores.get("chave_api"):
        from financeiro.models import GatewayConfig

        config, _ = GatewayConfig.todos.get_or_create(rede=rede, defaults={"gateway": "asaas"})
        config.gateway = "asaas"
        config.ambiente = valores.get("ambiente") or "sandbox"
        config.access_token = valores.get("chave_api", "")
        config.public_key = valores.get("chave_pix", "")
        config.ativo = bool(registro.ativo)
        config.save()
        espelhados.append("financeiro.GatewayConfig")

    if registro.provedor == "nfse":
        from fiscal.models import ConfiguracaoFiscal

        config, _ = ConfiguracaoFiscal.objects.get_or_create(rede=rede)
        config.provedor = valores.get("provedor") or config.provedor
        config.ambiente = valores.get("ambiente") or "homologacao"
        config.token = valores.get("token", "")
        config.inscricao_municipal = valores.get("inscricao_municipal", "")
        config.municipio = valores.get("municipio", "")
        if valores.get("codigo_do_servico"):
            config.codigo_do_servico = valores["codigo_do_servico"]
        aliquota = _decimal(valores.get("aliquota_iss"))
        if aliquota is not None:
            config.aliquota_iss = aliquota
        if valores.get("serie"):
            config.serie = valores["serie"]
        config.emissao_automatica = bool(valores.get("emitir_automaticamente"))
        config.save()
        espelhados.append("fiscal.ConfiguracaoFiscal")

    if registro.provedor == "smtp" and valores.get("host"):
        from notificacoes.models import ConfiguracaoEmail

        config = ConfiguracaoEmail.todos.filter(rede=rede).first() or ConfiguracaoEmail(rede=rede)
        config.host = valores.get("host", "")
        config.port = int(valores.get("porta") or 587)
        config.username = valores.get("usuario", "") or config.username
        if valores.get("senha"):
            config.password = valores["senha"]
        config.use_tls = bool(valores.get("usar_tls", True))
        config.remetente_nome = valores.get("remetente_nome") or "Academia System"
        config.remetente_email = valores.get("remetente_email") or config.username
        config.ativo = bool(registro.ativo)
        config.save()
        espelhados.append("notificacoes.ConfiguracaoEmail")

    if registro.provedor == "whatsapp" and valores.get("chave_api"):
        from notificacoes.models import ConfiguracaoWhatsapp

        config = ConfiguracaoWhatsapp.todos.filter(rede=rede).first() or ConfiguracaoWhatsapp(
            rede=rede
        )
        config.access_token = valores.get("chave_api", "")
        config.phone_number_id = valores.get("numero_remetente", "")
        config.business_account_id = valores.get("conta_comercial") or None
        config.ativo = bool(registro.ativo)
        config.save()
        espelhados.append("notificacoes.ConfiguracaoWhatsapp")

    return espelhados
