"""Seguranca do painel: rate limit de login, 2FA, midia protegida e dado sensivel.

Reune as regras de RNF-009, RNF-010 e RNF-006 (LGPD) num so lugar, para o
middleware, as views e os testes usarem a mesma fonte de verdade.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import unicodedata

from django.core.cache import cache
from django.utils import timezone

from core import totp

logger = logging.getLogger("seguranca")

#: bloqueio progressivo por tentativas erradas (segundos de espera por faixa)
FAIXAS_DE_BLOQUEIO = ((10, 1800), (5, 300), (3, 60))
JANELA_DE_TENTATIVAS_MINUTOS = 15
MAXIMO_DE_CODIGOS_DE_RECUPERACAO = 8
CHAVE_SESSAO_2FA = "dois_fatores_ok"
SEGUNDOS_DE_VALIDADE_DA_SESSAO_2FA = 60 * 60 * 12
PAPEIS_COM_DADO_SENSIVEL = {"admin_rede", "professor", "superadmin_plataforma"}


# ------------------------------------------------------------------ rate limit
def _chave(prefixo: str, valor: str) -> str:
    return f"{prefixo}:{hashlib.sha256((valor or '').encode()).hexdigest()[:32]}"


def bloqueio_ativo(identificador: str = "", ip: str = "") -> tuple[bool, int, int]:
    """(bloqueado, segundos_restantes, tentativas_recentes) para identificador e IP."""
    tentativas = max(
        cache.get(_chave("login:falhas:email", identificador), 0) or 0,
        cache.get(_chave("login:falhas:ip", ip), 0) or 0,
    )
    for limite, espera in FAIXAS_DE_BLOQUEIO:
        if tentativas >= limite:
            restante = cache.get(_chave("login:espera:segundos", f"{identificador}{ip}"), espera)
            return True, int(restante or espera), tentativas
    return False, 0, tentativas


def registrar_falha_de_login(identificador: str = "", ip: str = "") -> None:
    for prefixo, valor in (("email", identificador), ("ip", ip)):
        chave = _chave(f"login:falhas:{prefixo}", valor)
        try:
            cache.incr(chave)
        except ValueError:
            cache.set(chave, 1, JANELA_DE_TENTATIVAS_MINUTOS * 60)
    tentativas = max(
        cache.get(_chave("login:falhas:email", identificador), 0) or 0,
        cache.get(_chave("login:falhas:ip", ip), 0) or 0,
    )
    for limite, espera in FAIXAS_DE_BLOQUEIO:
        if tentativas >= limite:
            cache.set(_chave("login:espera", f"{identificador}{ip}"), espera, espera + 60)
            cache.set(_chave("login:espera:segundos", f"{identificador}{ip}"), espera, espera + 60)
            break


def limpar_falhas_de_login(identificador: str = "", ip: str = "") -> None:
    cache.delete(_chave("login:falhas:email", identificador))
    cache.delete(_chave("login:falhas:ip", ip))
    cache.delete(_chave("login:espera", f"{identificador}{ip}"))
    cache.delete(_chave("login:espera:segundos", f"{identificador}{ip}"))


# ------------------------------------------------------------------ 2FA
def dispositivo_do(usuario):
    from governanca.models import Dispositivo2FA

    if not getattr(usuario, "is_authenticated", False):
        return None
    return Dispositivo2FA.objects.filter(usuario=usuario).first()


def dois_fatores_ativo(usuario) -> bool:
    dispositivo = dispositivo_do(usuario)
    return bool(dispositivo and dispositivo.confirmado_em)


def iniciar_2fa(usuario):
    """Cria (ou recria) o segredo; ainda nao vale ate confirmar com um codigo."""
    from governanca.models import Dispositivo2FA

    segredo = totp.gerar_segredo()
    dispositivo, _ = Dispositivo2FA.objects.update_or_create(
        usuario=usuario, defaults={"segredo": segredo, "confirmado_em": None},
    )
    return dispositivo


def confirmar_2fa(usuario, codigo: str) -> bool:
    dispositivo = dispositivo_do(usuario)
    if dispositivo is None or not totp.validar(dispositivo.segredo, codigo):
        return False
    dispositivo.confirmado_em = timezone.now()
    dispositivo.save(update_fields=["confirmado_em"])
    return True


def validar_segundo_fator(usuario, codigo: str) -> bool:
    dispositivo = dispositivo_do(usuario)
    if dispositivo is None:
        return False
    if totp.validar(dispositivo.segredo, codigo):
        dispositivo.ultimo_uso_em = timezone.now()
        dispositivo.save(update_fields=["ultimo_uso_em"])
        return True
    return usar_codigo_de_recuperacao(usuario, codigo)


def desativar_2fa(usuario) -> None:
    from governanca.models import CodigoRecuperacao, Dispositivo2FA

    Dispositivo2FA.objects.filter(usuario=usuario).delete()
    CodigoRecuperacao.objects.filter(usuario=usuario).delete()


def gerar_codigos_de_recuperacao(usuario, quantidade: int = MAXIMO_DE_CODIGOS_DE_RECUPERACAO) -> list[str]:
    """Devolve os codigos em texto puro UMA vez; guarda apenas o hash."""
    from governanca.models import CodigoRecuperacao

    CodigoRecuperacao.objects.filter(usuario=usuario).delete()
    codigos = []
    for _ in range(quantidade):
        codigo = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper()
        CodigoRecuperacao.objects.create(
            usuario=usuario, hash_codigo=CodigoRecuperacao.gerar_hash(codigo),
        )
        codigos.append(codigo)
    return codigos


def usar_codigo_de_recuperacao(usuario, codigo: str) -> bool:
    from governanca.models import CodigoRecuperacao

    normalizado = (codigo or "").strip().upper()
    if not normalizado:
        return False
    registro = CodigoRecuperacao.objects.filter(
        usuario=usuario, hash_codigo=CodigoRecuperacao.gerar_hash(normalizado), usado_em__isnull=True,
    ).first()
    if registro is None:
        return False
    registro.usado_em = timezone.now()
    registro.save(update_fields=["usado_em"])
    return True


def marcar_sessao_verificada(request) -> None:
    request.session[CHAVE_SESSAO_2FA] = timezone.now().timestamp()


def sessao_verificada(request) -> bool:
    if dois_fatores_ativo(getattr(request, "user", None)) is False:
        return True  # sem 2FA ativo nao ha o que cobrar
    momento = request.session.get(CHAVE_SESSAO_2FA)
    if not momento:
        return False
    return (timezone.now().timestamp() - float(momento)) < SEGUNDOS_DE_VALIDADE_DA_SESSAO_2FA


def exigir_2fa_para(usuario) -> bool:
    """Equipe da plataforma e obrigada a usar 2FA (RNF-009)."""
    return bool(getattr(usuario, "is_staff", False) or getattr(usuario, "is_superuser", False))


# ------------------------------------------------------------------ midia (RNF-010)
def prefixo_de_midia(rede) -> str:
    base = (getattr(rede, "slug", "") or "sem-rede").strip().lower()
    apenas_seguro = "".join(c for c in base if c.isalnum() or c in "-_")
    return apenas_seguro or "sem-rede"


def caminho_e_do_tenant(caminho: str, rede) -> bool:
    """Confere se o arquivo esta no namespace do cliente (nunca aceita subir de pasta)."""
    if not caminho or not rede:
        return False
    partes = [pedaco for pedaco in str(caminho).replace("\\", "/").split("/") if pedaco not in ("", ".")]
    if any(pedaco == ".." for pedaco in partes):
        return False
    return len(partes) >= 2 and partes[0] == "redes" and partes[1] == prefixo_de_midia(rede)


def redes_do_usuario(usuario):
    if not getattr(usuario, "is_authenticated", False):
        return []
    from core.models import Rede

    if getattr(usuario, "is_superuser", False) or getattr(usuario, "is_staff", False):
        return list(Rede.todos.all())
    return list(Rede.todos.filter(vinculos__usuario=usuario, vinculos__ativo=True).distinct())


def acesso_a_midia_permitido(usuario, caminho: str) -> bool:
    """Arquivo de midia so e servido para quem tem vinculo com o cliente dono dele."""
    if not getattr(usuario, "is_authenticated", False):
        return False
    return any(caminho_e_do_tenant(caminho, rede) for rede in redes_do_usuario(usuario))


# ------------------------------------------------------------------ dado sensivel (LGPD)
def papel_permite_dado_sensivel(papeis) -> bool:
    return bool(set(papeis or []) & PAPEIS_COM_DADO_SENSIVEL)


def registrar_acesso_sensivel(rede, usuario, titular, origem="painel", acao="leitura"):
    """RNF-006e: toda leitura de ficha de saude fica registrada."""
    from governanca.models import AcessoDadoSensivel

    try:
        return AcessoDadoSensivel.objects.create(
            rede=rede, usuario=usuario if getattr(usuario, "pk", None) else None,
            titular_nome=getattr(titular, "nome", str(titular))[:150],
            usuario_id_titular=getattr(titular, "pk", None), origem=origem, acao=acao,
        )
    except Exception as erro:  # noqa: BLE001 - auditoria nunca derruba a tela
        logger.warning("falha ao registrar acesso a dado sensivel: %s", erro)
        return None


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").strip().lower())
    return "".join(c for c in base if not unicodedata.combining(c))
