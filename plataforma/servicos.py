"""Regras da plataforma: limites, faturas, regua de cobranca, metricas e suporte."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from api.auditoria import registrar
from core.models import ConviteEquipe, Rede, Unidade, VinculoUsuario
from core.papeis import Papel, StatusRede
from plataforma.gateways import GatewayError, gateway_atual
from plataforma.models import (
    Assinatura,
    CanalCobranca,
    ConfiguracaoPlataforma,
    EventoCobranca,
    EventoGateway,
    Fatura,
    FormaPagamento,
    Impersonacao,
    MarcoRegua,
    ResultadoDisparo,
    StatusFatura,
)
from professores.models import Professor
from usuarios.models import Usuario

logger = logging.getLogger("plataforma")

RECURSOS = ("alunos", "professores", "unidades")
CHAVE_IMPERSONACAO = "impersonacao_id"


class CadastroError(Exception):
    """Cadastro publico recusado; a mensagem ja esta pronta para o cliente ver."""


# ------------------------------------------------------------------ LIMITES
def assinatura_da(rede) -> Assinatura | None:
    if rede is None:
        return None
    return Assinatura.objects.filter(rede=rede).select_related("pacote").first()


def uso_do_tenant(rede) -> dict[str, int]:
    """Uso que conta para o limite: so cadastros ativos (PRD 4.2)."""
    if rede is None:
        return dict.fromkeys(RECURSOS, 0)
    return {
        "alunos": Usuario.todos.filter(
            rede=rede, status_user="Ativo", arquivado_em__isnull=True
        ).count(),
        "professores": Professor.todos.filter(
            rede=rede, status_prof="Ativo", arquivado_em__isnull=True
        ).count(),
        "unidades": Unidade.todos.filter(rede=rede).exclude(status="inativa").count(),
    }


def limites_efetivos(rede) -> dict[str, int | None]:
    assinatura = assinatura_da(rede)
    if assinatura is None:
        return dict.fromkeys(RECURSOS, None)
    return assinatura.limites_efetivos()


def percentual_de_uso(uso: int, limite: int | None) -> int:
    if not limite:
        return 0
    return round(100 * uso / limite)


def pode_cadastrar(rede, recurso: str) -> tuple[bool, str]:
    """RF-TEN-040: recusa no teto com mensagem acionavel."""
    if recurso not in RECURSOS:
        raise ValueError(f"recurso desconhecido: {recurso}")
    assinatura = assinatura_da(rede)
    if assinatura is None:
        return True, ""
    limite = assinatura.limite_efetivo(recurso)
    if limite is None:
        return True, ""
    uso = uso_do_tenant(rede)[recurso]
    if uso < limite:
        return True, ""
    return False, (
        f"Seu pacote {assinatura.pacote.nome} permite {limite} {recurso} ativos e voce ja tem "
        f"{uso}. Arquive {recurso} inativos ou mude de pacote em Meu plano."
    )


def modulo_disponivel(rede, modulo: str) -> bool:
    """Feature flag do pacote (RF-PLT-011). Sem assinatura, tudo liberado (compatibilidade)."""
    assinatura = assinatura_da(rede)
    if assinatura is None:
        return True
    return assinatura.tem_modulo(modulo)


# ------------------------------------------------------- ARMAZENAMENTO E COMPRA
def limite_de_armazenamento(rede) -> int | None:
    """Teto de armazenamento do tenant em **bytes** (``None`` = sem teto).

    O pacote guarda o limite em GB; aqui vira byte porque e assim que o envio de midia
    compara com o tamanho do arquivo.
    """
    assinatura = assinatura_da(rede)
    if assinatura is None:
        return None
    gb = assinatura.limite_efetivo("armazenamento")
    return None if not gb else int(gb) * 1024**3


def uso_de_armazenamento(rede) -> int:
    """Bytes ja ocupados pela rede (midia removida nao conta)."""
    from django.db.models import Sum

    from midia.models import ArquivoDeMidia

    total = (
        ArquivoDeMidia.objects.filter(rede=rede)
        .exclude(situacao=ArquivoDeMidia.Situacao.REMOVIDO)
        .aggregate(total=Sum("tamanho_bytes"))["total"]
        or 0
    )
    return int(total)


def espaco_disponivel(rede, bytes_novos: int = 0) -> tuple[bool, str]:
    """Diz se o arquivo cabe no pacote (mensagem pronta quando nao cabe)."""
    from core.validadores import tamanho_legivel

    limite = limite_de_armazenamento(rede)
    if limite is None:
        return True, ""
    usado = uso_de_armazenamento(rede)
    disponivel = max(limite - usado, 0)
    if bytes_novos and bytes_novos > disponivel:
        pacote = getattr(assinatura_da(rede), "pacote", None)
        nome = getattr(pacote, "nome", "atual")
        return False, (
            f"Espaco insuficiente no pacote {nome}: o plano guarda {tamanho_legivel(limite)}, "
            f"ja em uso {tamanho_legivel(usado)} e este arquivo tem "
            f"{tamanho_legivel(bytes_novos)}. Remova midia antiga ou mude de pacote."
        )
    return True, ""


def compra_de_pacote_liberada() -> bool:
    """Interruptor da plataforma (Django admin): a compra de pacote nasce **desligada**."""
    return bool(ConfiguracaoPlataforma.obter().permitir_compra_de_pacote)


def alertas_de_limite(rede) -> list[dict]:
    """Avisos de 80% e 95% (RF-TEN-041) calculados na hora."""
    assinatura = assinatura_da(rede)
    if assinatura is None:
        return []
    uso = uso_do_tenant(rede)
    avisos = []
    for recurso in RECURSOS:
        limite = assinatura.limite_efetivo(recurso)
        if not limite:
            continue
        percentual = percentual_de_uso(uso[recurso], limite)
        if percentual >= 95:
            avisos.append({"recurso": recurso, "percentual": percentual, "nivel": "critico"})
        elif percentual >= 80:
            avisos.append({"recurso": recurso, "percentual": percentual, "nivel": "atencao"})
    return avisos


def situacao_do_tenant(rede) -> dict:
    """Resumo de plano/uso para o painel do tenant e para a plataforma."""
    assinatura = assinatura_da(rede)
    uso = uso_do_tenant(rede)
    limites = limites_efetivos(rede)
    recursos = [
        {
            "recurso": recurso,
            "uso": uso[recurso],
            "limite": limites[recurso],
            "percentual": percentual_de_uso(uso[recurso], limites[recurso]),
            "ilimitado": limites[recurso] is None,
        }
        for recurso in RECURSOS
    ]
    return {
        "assinatura": assinatura,
        "pacote": getattr(assinatura, "pacote", None),
        "uso": uso,
        "limites": limites,
        "recursos": recursos,
        "alertas": alertas_de_limite(rede),
        "em_trial": bool(assinatura and assinatura.em_trial),
        "trial_termina_em": getattr(assinatura, "trial_termina_em", None),
        "faturas_em_aberto": Fatura.objects.filter(
            rede=rede,
            status__in=[
                StatusFatura.ABERTA,
                StatusFatura.VENCIDA,
            ],
        ).order_by("vencimento"),
        "modulos": list(getattr(getattr(assinatura, "pacote", None), "modulos", []) or []),
    }


# ------------------------------------------------------------------ COBRANCA
def gerar_fatura(assinatura: Assinatura, hoje=None, vencimento=None) -> Fatura | None:
    """Gera a fatura do ciclo. Idempotente por periodo (nao duplica)."""
    hoje = hoje or timezone.localdate()
    if assinatura.cancelada:
        return None
    periodo_inicio = assinatura.renovacao_em or hoje
    periodo_fim = Fatura.proximo_vencimento(periodo_inicio, assinatura.ciclo)
    existe = Fatura.objects.filter(
        assinatura=assinatura,
        periodo_inicio=periodo_inicio,
        status__in=[
            StatusFatura.ABERTA,
            StatusFatura.VENCIDA,
            StatusFatura.PAGA,
        ],
    ).first()
    if existe:
        return None
    valor = assinatura.valor_do_ciclo()
    fatura = Fatura.objects.create(
        rede=assinatura.rede,
        assinatura=assinatura,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        vencimento=vencimento or periodo_inicio,
        valor=valor,
        valor_final=valor,
        observacao=f"Assinatura {assinatura.pacote.nome} ({assinatura.ciclo})",
    )
    return fatura


def gerar_faturas_do_dia(hoje=None, emitir_cobranca: bool = True) -> list[Fatura]:
    """Faturas para assinaturas cujo ciclo vence hoje (ou ja venceu)."""
    hoje = hoje or timezone.localdate()
    geradas = []
    assinaturas = Assinatura.objects.select_related("rede", "pacote").filter(
        cancelada_em__isnull=True,
        renovacao_em__lte=hoje,
    )
    for assinatura in assinaturas:
        if assinatura.em_trial:
            continue
        fatura = gerar_fatura(assinatura, hoje=hoje)
        if fatura is None:
            continue
        assinatura.renovacao_em = Fatura.proximo_vencimento(
            assinatura.renovacao_em, assinatura.ciclo
        )
        assinatura.save(update_fields=["renovacao_em", "atualizado_em"])
        if emitir_cobranca:
            fatura = emitir_cobranca_da_fatura(fatura)
        geradas.append(fatura)
    return geradas


def emitir_cobranca_da_fatura(fatura: Fatura) -> Fatura:
    """Cria a cobranca no gateway (Pix) e guarda QR/copia-e-cola/link."""
    gateway = gateway_atual()
    try:
        dados = gateway.criar_cobranca(fatura)
    except GatewayError as erro:
        logger.warning("Gateway indisponivel para a fatura %s: %s", fatura.numero, erro)
        registrar(
            "cobrar", "fatura", entidade_id=fatura.pk, descricao=f"Falha ao emitir cobranca: {erro}"
        )
        return fatura
    fatura.gateway = gateway.nome
    fatura.gateway_id = dados.get("id", "")
    fatura.link_pagamento = dados.get("link_pagamento", "")
    fatura.pix_copia_cola = dados.get("pix_copia_cola", "")
    fatura.pix_qr_code = dados.get("pix_qr_code", "")
    fatura.save()
    registrar(
        "cobrar",
        "fatura",
        entidade_id=fatura.pk,
        descricao=f"Cobranca emitida via {gateway.nome} ({fatura.valor_final})",
    )
    return fatura


def _disparar_email(rede, assunto: str, corpo: str) -> tuple[bool, str]:
    from gestao.emails import enviar_email

    destino = [rede.email_responsavel] if rede.email_responsavel else []
    if not destino:
        return False, "sem e-mail do responsavel cadastrado"
    try:
        enviar_email(rede, assunto, corpo, destino)
        return True, ""
    except Exception as erro:
        return False, str(erro)[:200]


def _registrar_marco(fatura, rede, marco: str, assunto: str, corpo: str, canal=CanalCobranca.EMAIL):
    """Registra o disparo da regua (unico por fatura+marco+canal)."""
    ja_existe = EventoCobranca.objects.filter(fatura=fatura, marco=marco, canal=canal).exists()
    if ja_existe:
        return None
    enviado, erro = (False, "canal painel nao envia e-mail")
    if canal == CanalCobranca.EMAIL:
        enviado, erro = _disparar_email(rede, assunto, corpo)
    return EventoCobranca.objects.create(
        fatura=fatura,
        rede=rede,
        marco=marco,
        canal=canal,
        status=ResultadoDisparo.ENVIADO if enviado else ResultadoDisparo.FALHA,
        mensagem=corpo[:4000],
        erro=erro,
    )


def aplicar_regua(hoje=None, enviar: bool = True) -> dict:
    """RF-PLT-023: D-3, D0, D+1, D+5, D+10 (bloqueio) e D+30 (suspensao), sem repetir."""
    hoje = hoje or timezone.localdate()
    configuracao = ConfiguracaoPlataforma.obter()
    resumo = {
        "disparos": 0,
        "bloqueios": 0,
        "suspensoes": 0,
        "reativacoes": 0,
        "faturas_vencidas": 0,
    }
    if not configuracao.regua_ativa:
        return resumo

    for assinatura in Assinatura.objects.select_related("rede").filter(cancelada_em__isnull=True):
        rede = assinatura.rede
        if assinatura.trial_termina_em:
            faltam = (assinatura.trial_termina_em - hoje).days
            for marco, dias in (
                (MarcoRegua.TRIAL_7, 7),
                (MarcoRegua.TRIAL_3, 3),
                (MarcoRegua.TRIAL_1, 1),
            ):
                if faltam == dias:
                    enviado = _registrar_marco(
                        None,
                        rede,
                        marco,
                        f"Seu teste do pacote {assinatura.pacote.nome} termina em {dias} dia(s)",
                        f"Faltam {dias} dia(s) para o fim do periodo de teste da {rede.nome}.",
                    )
                    if enviado:
                        resumo["disparos"] += 1
            if faltam < 0 and rede.status == StatusRede.TRIAL:
                rede.status = StatusRede.SOMENTE_LEITURA
                rede.save(update_fields=["status"])
                resumo["bloqueios"] += 1

    faturas = Fatura.objects.select_related("rede", "assinatura").filter(
        status__in=[StatusFatura.ABERTA, StatusFatura.VENCIDA]
    )
    for fatura in faturas:
        atraso = (hoje - fatura.vencimento).days
        rede = fatura.rede
        marcos = [
            (-3, MarcoRegua.D3, "Sua fatura vence em 3 dias"),
            (0, MarcoRegua.D0, "Sua fatura vence hoje"),
            (1, MarcoRegua.D1, "Sua fatura esta atrasada"),
            (5, MarcoRegua.D5, "Aviso de bloqueio: regularize sua fatura"),
            (configuracao.dias_bloqueio, MarcoRegua.D10, "Escrita bloqueada por inadimplencia"),
            (configuracao.dias_suspensao, MarcoRegua.D30, "Conta suspensa por inadimplencia"),
        ]
        for dias, marco, assunto in marcos:
            if dias < 0:
                if atraso != dias:  # marco de pre-vencimento: so no dia exato
                    continue
            elif atraso < dias:
                continue
            disparo = _registrar_marco(
                fatura,
                rede,
                marco,
                f"{assunto} - {fatura.numero}",
                f"{assunto}. Fatura {fatura.numero}, vencimento {fatura.vencimento:%d/%m/%Y}, "
                f"valor {fatura.valor_final}. Ao pagar, o acesso e restabelecido automaticamente.",
            )
            if disparo:
                resumo["disparos"] += 1
            if (
                marco == MarcoRegua.D10
                and dias > 0
                and rede.status not in {StatusRede.SUSPENSO, StatusRede.CANCELADO}
            ):
                rede.status = StatusRede.SOMENTE_LEITURA
                rede.save(update_fields=["status"])
                resumo["bloqueios"] += 1
            if marco == MarcoRegua.D30 and rede.status not in {StatusRede.CANCELADO}:
                rede.status = StatusRede.SUSPENSO
                rede.save(update_fields=["status"])
                resumo["suspensoes"] += 1
        if fatura.status == StatusFatura.ABERTA and atraso > 0:
            fatura.status = StatusFatura.VENCIDA
            fatura.save(update_fields=["status"])
            resumo["faturas_vencidas"] += 1
    return resumo


def processar_evento_gateway(payload: dict, gateway: str = "asaas") -> tuple[EventoGateway, bool]:
    """RF-PLT-022: baixa automatica tolerante a notificacao repetida."""
    evento_id = str(payload.get("id") or payload.get("eventId") or "").strip()
    if not evento_id:
        raise ValueError("evento sem id")
    evento, criado = EventoGateway.objects.get_or_create(
        gateway=gateway,
        evento_id=evento_id,
        defaults={"tipo": payload.get("event", ""), "payload": payload},
    )
    if not criado:
        evento.resultado = "repetido (ignorado)"
        evento.save(update_fields=["resultado"])
        return evento, False

    pagamento = payload.get("payment") or {}
    identificador = str(pagamento.get("id") or payload.get("paymentId") or "")
    resultado = "sem pagamento no evento"
    if identificador:
        fatura = Fatura.objects.select_related("rede").filter(gateway_id=identificador).first()
        if fatura is None:
            resultado = f"fatura nao encontrada para {identificador}"
        else:
            status_gateway = str(pagamento.get("status", "")).upper()
            if status_gateway in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}:
                pago_agora = fatura.marcar_paga(
                    valor_pago=pagamento.get("value"),
                    forma=FormaPagamento.PIX,
                    gateway_id=identificador,
                )
                resultado = "fatura paga" if pago_agora else "fatura ja estava paga"
                if pago_agora:
                    _reativar_rede(fatura.rede)
            elif status_gateway in {"REFUNDED", "CHARGEBACK_REQUESTED"}:
                fatura.status = StatusFatura.ESTORNADA
                fatura.save(update_fields=["status"])
                resultado = "fatura estornada"
            else:
                resultado = f"status ignorado: {status_gateway or 'vazio'}"
    evento.processado_em = timezone.now()
    evento.resultado = resultado
    evento.save(update_fields=["processado_em", "resultado"])
    registrar(
        "cobrar",
        "evento_gateway",
        entidade_id=evento.pk,
        descricao=f"{gateway}:{evento_id} -> {resultado}",
    )
    return evento, True


def _reativar_rede(rede) -> bool:
    if rede.status in {StatusRede.SOMENTE_LEITURA, StatusRede.INADIMPLENTE, StatusRede.SUSPENSO}:
        rede.status = StatusRede.ATIVO
        rede.save(update_fields=["status"])
        registrar(
            "reativar",
            "rede",
            entidade_id=rede.pk,
            descricao="Tenant reativado automaticamente apos pagamento",
        )
        return True
    return False


# ------------------------------------------------------------------ CADASTRO PUBLICO
def slug_disponivel(slug: str) -> tuple[bool, str]:
    from plataforma.validadores import validar_slug

    valido, mensagem = validar_slug(slug)
    if not valido:
        return False, mensagem
    if Rede.todos.filter(slug=slug.strip().lower()).exists():
        return False, "Esse identificador ja esta em uso. Escolha outro."
    return True, ""


def cnpj_em_uso(cnpj: str) -> bool:
    from plataforma.validadores import normalizar_cnpj

    limpo = normalizar_cnpj(cnpj)
    if not limpo:
        return False
    return any(normalizar_cnpj(rede.cnpj) == limpo for rede in Rede.todos.exclude(cnpj=""))


def _criar_configuracoes_padrao(rede, nome: str) -> None:
    """Configuracao e identidade visual padrao (RF-PLT-031)."""
    from academia.models import Configuracao, IdentidadeVisual

    Configuracao.todos.get_or_create(
        rede=rede,
        defaults={"titulo": nome, "theme_mode": "light"},
    )
    # Identidade visual padrao: o tenant nasce apontando para os assets estaticos do
    # projeto (o painel cai no logo padrao quando o campo esta vazio).
    IdentidadeVisual.todos.get_or_create(rede=rede, defaults={})


def criar_convite_do_dono(rede, email: str, papel=Papel.ADMIN_REDE, dias: int = 7):
    """Convite de primeiro acesso: a pessoa define a propria senha (nunca senha por e-mail)."""
    from datetime import timedelta

    return ConviteEquipe.objects.create(
        rede=rede,
        unidade=None,
        email=email.strip().lower(),
        papel=papel,
        papeis=[papel],
        token=ConviteEquipe.gerar_token(),
        expira_em=timezone.now() + timedelta(days=dias),
    )


def link_do_convite(request, convite) -> str:
    from django.urls import reverse

    caminho = reverse("gestao:convite_aceitar", args=[convite.token])
    if request is not None:
        return request.build_absolute_uri(caminho)
    return caminho


def enviar_boas_vindas(request, rede, convite, fatura=None, trial_dias=None) -> bool:
    """E-mail de boas-vindas do cadastro (RF-PLT-032)."""
    from plataforma.emails import enviar_email_plataforma

    link = link_do_convite(request, convite)
    linhas = [
        f"Bem-vindo(a) ao Academia SaaS, {rede.nome}!",
        "",
        "Sua conta foi criada e ja esta pronta para uso. Para entrar:",
        "",
        f"1. Defina sua senha de acesso: {link}",
        "2. Complete a configuracao pelo assistente (marca, unidade, professores e planos).",
        "",
    ]
    if trial_dias:
        linhas.append(
            f"Voce esta no periodo de teste do pacote {convite.rede.assinatura.pacote.nome} "
            f"por {trial_dias} dias -- sem cobranca nesse periodo."
        )
    if fatura is not None:
        linhas.append(
            f"Fatura {fatura.numero}: R$ {fatura.valor_final} com vencimento em "
            f"{fatura.vencimento:%d/%m/%Y}."
        )
        if fatura.pix_copia_cola:
            linhas.append(f"Pix copia e cola: {fatura.pix_copia_cola}")
        if fatura.link_pagamento:
            linhas.append(f"Link de pagamento: {fatura.link_pagamento}")
    linhas += ["", "Qualquer duvida, responda este e-mail.", "", "Equipe SafeStack"]
    return enviar_email_plataforma(
        f"Bem-vindo(a) ao Academia SaaS - {rede.nome}",
        "\n".join(linhas),
        [rede.email_responsavel or convite.email],
    )


@transaction.atomic
def cadastrar_tenant_publico(
    *,
    nome,
    slug,
    cnpj,
    responsavel,
    email,
    telefone,
    pacote,
    modalidade="trial",
    dominio="",
    request=None,
) -> dict:
    """Cadastro self-service (RF-PLT-030/031): tudo ou nada.

    ``modalidade``: ``trial`` (teste de 14 dias no pacote escolhido) ou
    ``pagamento`` (assina agora, com a primeira fatura em Pix).
    """
    from plataforma.validadores import normalizar_cnpj, sugerir_slug, validar_cnpj

    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    if not nome:
        raise CadastroError("Informe o nome da academia.")
    if not email or "@" not in email:
        raise CadastroError("Informe um e-mail valido do responsavel.")
    cnpj_limpo = normalizar_cnpj(cnpj)
    if cnpj_limpo and not validar_cnpj(cnpj_limpo):
        raise CadastroError("O CNPJ informado nao e valido. Confira os numeros e tente novamente.")
    if cnpj_limpo and cnpj_em_uso(cnpj_limpo):
        raise CadastroError(
            "Ja existe uma academia cadastrada com este CNPJ. "
            "Fale com o suporte para recuperar o acesso."
        )
    slug = (slug or "").strip().lower() or sugerir_slug(nome)
    liberado, mensagem = slug_disponivel(slug)
    if not liberado:
        raise CadastroError(mensagem)
    if not pacote.ativo:
        raise CadastroError("Este pacote nao esta disponivel no momento.")
    if modalidade != "trial" and not compra_de_pacote_liberada():
        raise CadastroError(
            "A compra de pacote esta desabilitada nesta plataforma no momento. "
            "Comece pelo periodo de teste ou fale com o comercial para assinar."
        )

    configuracao = ConfiguracaoPlataforma.obter()
    hoje = timezone.localdate()
    usar_trial = modalidade == "trial"
    termina_em = timezone.now() + timedelta(days=configuracao.trial_dias) if usar_trial else None

    rede = Rede.todos.create(
        nome=nome,
        slug=slug,
        cnpj=cnpj_limpo,
        email_responsavel=email,
        telefone=telefone,
        dominio=dominio,
        status=StatusRede.TRIAL if usar_trial else StatusRede.ATIVO,
        trial_termina_em=termina_em,
        observacoes_internas=f"Cadastro self-service ({modalidade}) por {responsavel or 'nao informado'}",
    )
    assinatura = Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo="mensal",
        inicio=hoje,
        renovacao_em=(
            hoje + timedelta(days=configuracao.trial_dias)
            if usar_trial
            else Fatura.proximo_vencimento(hoje, "mensal")
        ),
        trial_termina_em=termina_em.date() if usar_trial else None,
    )
    _criar_configuracoes_padrao(rede, nome)

    usuario = get_user_model().objects.create(
        username=f"dono.{slug}"[:150],
        email=email,
        first_name=(responsavel or nome)[:150],
        is_staff=False,
    )
    usuario.set_unusable_password()
    usuario.save(update_fields=["password"])
    VinculoUsuario.todos.create(
        usuario=usuario, rede=rede, unidade=None, papel=Papel.ADMIN_REDE, ativo=True
    )

    convite = criar_convite_do_dono(rede, email)
    fatura = None
    if not usar_trial:
        fatura = gerar_fatura(assinatura, hoje=hoje, vencimento=hoje)
        if fatura is not None:
            fatura = emitir_cobranca_da_fatura(fatura)
    registrar(
        "criar",
        "rede",
        entidade_id=rede.pk,
        descricao=f"Cadastro self-service {rede.nome} ({pacote.nome}, {modalidade})",
        request=request,
    )
    enviado = enviar_boas_vindas(
        request,
        rede,
        convite,
        fatura=fatura,
        trial_dias=configuracao.trial_dias if usar_trial else None,
    )
    return {
        "rede": rede,
        "assinatura": assinatura,
        "usuario": usuario,
        "convite": convite,
        "fatura": fatura,
        "email_enviado": enviado,
        "link_primeiro_acesso": link_do_convite(request, convite),
    }


def aplicar_trocas_agendadas(hoje=None) -> int:
    """Aplica pacotes agendados no dia da renovacao (downgrade, PRD 11.3)."""
    hoje = hoje or timezone.localdate()
    aplicadas = 0
    for assinatura in Assinatura.objects.filter(pacote_agendado__isnull=False).select_related(
        "pacote"
    ):
        if assinatura.renovacao_em <= hoje:
            assinatura.aplicar_troca_agendada()
            aplicadas += 1
    return aplicadas


def trocar_pacote_do_tenant(rede, pacote, request=None, usuario=None) -> dict:
    """Upgrade imediato (fatura proporcional) ou downgrade no proximo ciclo (RF-TEN-040..043)."""
    assinatura = assinatura_da(rede)
    if assinatura is None:
        raise CadastroError("Esta academia ainda nao tem assinatura ativa.")
    if assinatura.pacote_id == pacote.pk:
        return {"tipo": "nenhuma", "aviso": "Voce ja esta neste pacote."}
    atual = assinatura.pacote
    subindo = (pacote.limite_alunos or 10**9) > (atual.limite_alunos or 10**9) or (
        pacote.limite_alunos is None and atual.limite_alunos is not None
    )
    if subindo:
        fatura = assinatura.trocar_pacote(pacote)
        if fatura is not None:
            fatura = emitir_cobranca_da_fatura(fatura)
        registrar(
            "alterar",
            "assinatura",
            entidade_id=assinatura.pk,
            descricao=f"Upgrade para {pacote.nome} via painel do cliente",
            request=request,
        )
        return {
            "tipo": "upgrade",
            "fatura": fatura,
            "aviso": (
                f"Upgrade para {pacote.nome} aplicado. "
                + (
                    f"Fatura proporcional {fatura.numero} emitida."
                    if fatura
                    else "Nenhum valor proporcional a cobrar neste ciclo."
                )
            ),
        }
    assinatura.agendar_troca(pacote)
    uso = uso_do_tenant(rede)
    excedente = []
    for recurso in RECURSOS:
        limite = pacote.limite_de(recurso)
        if limite is not None and uso[recurso] > limite:
            excedente.append(f"{uso[recurso]} {recurso} (limite {limite})")
    aviso = (
        f"Downgrade para {pacote.nome} agendado para {assinatura.renovacao_em:%d/%m/%Y}. "
        "Nada e apagado."
    )
    if excedente:
        aviso += (
            " Atencao: voce ja usa acima do novo limite ("
            + "; ".join(excedente)
            + ") -- cadastros novos ficarao bloqueados ate regularizar."
        )
    registrar(
        "alterar",
        "assinatura",
        entidade_id=assinatura.pk,
        descricao=f"Downgrade agendado para {pacote.nome} via painel do cliente",
        request=request,
    )
    return {"tipo": "downgrade", "fatura": None, "aviso": aviso}


# ------------------------------------------------------------------ METRICAS
def metricas(hoje=None) -> dict:
    """MRR, ARR, churn, inadimplencia e distribuicao por pacote (RF-PLT-006)."""
    hoje = hoje or timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    assinaturas = list(
        Assinatura.objects.select_related("pacote", "rede").filter(cancelada_em__isnull=True)
    )
    mrr = Decimal("0")
    por_pacote: dict[str, dict] = {}
    for assinatura in assinaturas:
        valor = assinatura.valor_do_ciclo()
        mensal = valor if assinatura.ciclo == "mensal" else (valor / 12).quantize(Decimal("0.01"))
        mrr += mensal
        chave = assinatura.pacote.nome
        item = por_pacote.setdefault(chave, {"pacote": chave, "tenants": 0, "mrr": Decimal("0")})
        item["tenants"] += 1
        item["mrr"] += mensal

    canceladas_mes = Assinatura.objects.filter(cancelada_em__gte=inicio_mes).count()
    ativas_no_inicio = len(assinaturas) + canceladas_mes
    faturas_abertas = Fatura.objects.filter(status__in=[StatusFatura.ABERTA, StatusFatura.VENCIDA])
    inadimplentes = faturas_abertas.filter(vencimento__lt=hoje).values("rede").distinct().count()
    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "tenants_ativos": len(assinaturas),
        "tenants_trial": sum(1 for a in assinaturas if a.em_trial),
        "tenants_inadimplentes": inadimplentes,
        "tenants_suspensos": Rede.objects.filter(status=StatusRede.SUSPENSO).count(),
        "churn_mes": canceladas_mes,
        "churn_percentual": round(100 * canceladas_mes / ativas_no_inicio, 1)
        if ativas_no_inicio
        else 0,
        "ticket_medio": (mrr / len(assinaturas)).quantize(Decimal("0.01"))
        if assinaturas
        else Decimal("0"),
        "novos_tenants_mes": Rede.objects.filter(criado_em__date__gte=inicio_mes).count(),
        "por_pacote": sorted(por_pacote.values(), key=lambda item: item["mrr"], reverse=True),
        "em_aberto": faturas_abertas.aggregate(total=Sum("valor_final"))["total"] or Decimal("0"),
        "recebido_mes": Fatura.objects.filter(
            status=StatusFatura.PAGA, pago_em__gte=inicio_mes
        ).aggregate(total=Sum("valor_final"))["total"]
        or Decimal("0"),
    }


# ------------------------------------------------------------------ PROVISIONAMENTO
@transaction.atomic
def provisionar_tenant(
    *,
    nome,
    slug,
    pacote,
    ciclo="mensal",
    cnpj="",
    email="",
    telefone="",
    trial=True,
    usuario_dono=None,
    dominio="",
) -> tuple[Rede, Assinatura]:
    """RF-PLT-002/031: cria o tenant completo (tudo ou nada)."""
    configuracao = ConfiguracaoPlataforma.obter()
    hoje = timezone.localdate()
    termina_em = timezone.now() + timedelta(days=configuracao.trial_dias) if trial else None
    rede = Rede.todos.create(
        nome=nome,
        slug=slug,
        cnpj=cnpj,
        email_responsavel=email,
        telefone=telefone,
        dominio=dominio,
        status=StatusRede.TRIAL if trial else StatusRede.ATIVO,
        trial_termina_em=termina_em,
    )
    assinatura = Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo=ciclo,
        inicio=hoje,
        renovacao_em=(
            hoje + timezone.timedelta(days=configuracao.trial_dias)
            if trial
            else Fatura.proximo_vencimento(hoje, ciclo)
        ),
        trial_termina_em=rede.trial_termina_em,
    )
    if usuario_dono is not None:
        VinculoUsuario.todos.get_or_create(
            usuario=usuario_dono,
            rede=rede,
            unidade=None,
            defaults={"papel": Papel.ADMIN_REDE, "ativo": True},
        )
    registrar(
        "criar",
        "rede",
        entidade_id=rede.pk,
        descricao=f"Tenant provisionado ({pacote.nome}, {'trial' if trial else 'ativo'})",
    )
    return rede, assinatura


# ------------------------------------------------------------------ SUPORTE
def e_equipe_plataforma(usuario) -> bool:
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser or usuario.is_staff:
        return True
    return VinculoUsuario.todos.filter(
        usuario=usuario, papel=Papel.SUPERADMIN_PLATAFORMA, ativo=True
    ).exists()


def impersonar(
    usuario_plataforma, rede, motivo: str, request=None, usuario_alvo: str = ""
) -> Impersonacao:
    """RF-PLT-007: motivo obrigatorio e registro imutavel."""
    if not (motivo or "").strip():
        raise ValueError("informe o motivo do acesso de suporte")
    ip = None
    user_agent = ""
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get(
            "REMOTE_ADDR"
        )
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:200]
    registro = Impersonacao.objects.create(
        rede=rede,
        usuario_plataforma=usuario_plataforma,
        usuario_alvo=usuario_alvo[:150],
        motivo=motivo.strip(),
        ip=ip,
        user_agent=user_agent,
    )
    if request is not None:
        request.session[CHAVE_IMPERSONACAO] = registro.pk
    registrar(
        "impersonar",
        "rede",
        entidade_id=rede.pk,
        descricao=f"Suporte acessou como {rede.nome}: {motivo.strip()[:120]}",
        request=request,
    )
    return registro


def impersonacao_ativa(request):
    """Impersonacao em curso nesta sessao (ou None)."""
    if request is None or not hasattr(request, "session"):
        return None
    identificador = request.session.get(CHAVE_IMPERSONACAO)
    if not identificador:
        return None
    registro = Impersonacao.objects.filter(pk=identificador, fim__isnull=True).first()
    if registro is None:
        request.session.pop(CHAVE_IMPERSONACAO, None)
    return registro


def encerrar_impersonacao(request):
    registro = impersonacao_ativa(request)
    if registro is None:
        return None
    registro.encerrar()
    request.session.pop(CHAVE_IMPERSONACAO, None)
    registrar(
        "impersonar",
        "rede",
        entidade_id=registro.rede_id,
        descricao=f"Acesso de suporte encerrado ({registro.rede.nome})",
        request=request,
    )
    return registro


def registrar_acao_impersonada(request, descricao: str) -> None:
    """Conta e audita cada acao feita durante a impersonation."""
    registro = impersonacao_ativa(request)
    if registro is None:
        return
    registro.acoes = registro.acoes + 1
    registro.save(update_fields=["acoes"])
    registrar(
        "impersonar",
        "acao_suporte",
        entidade_id=registro.rede_id,
        descricao=f"[suporte:{registro.usuario_plataforma}] {descricao[:180]}",
        request=request,
    )
