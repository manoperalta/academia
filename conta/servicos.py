"""Servicos de suporte e de sessao (perfil, sessoes ativas)."""

from __future__ import annotations

from django.contrib.sessions.models import Session
from django.utils import timezone

from conta.models import ChamadoDeSuporte, MensagemDoChamado


class ErroDeConta(Exception):
    """Falha esperada na conta ou no suporte."""


# ------------------------------------------------------------------ suporte
def abrir_chamado(
    *,
    rede,
    titulo: str,
    descricao: str,
    categoria: str = "duvida",
    prioridade: str = "normal",
    aberto_por=None,
    unidade=None,
    aluno=None,
) -> ChamadoDeSuporte:
    if not (titulo or "").strip():
        raise ErroDeConta("Dê um titulo ao chamado.")
    if not (descricao or "").strip():
        raise ErroDeConta("Descreva o que aconteceu — quanto mais detalhe, mais rapido resolver.")
    if categoria not in dict(ChamadoDeSuporte.Categoria.choices):
        raise ErroDeConta("Categoria de chamado desconhecida.")
    if prioridade not in dict(ChamadoDeSuporte.Prioridade.choices):
        raise ErroDeConta("Prioridade desconhecida.")
    return ChamadoDeSuporte.objects.create(
        rede=rede,
        unidade=unidade,
        titulo=titulo.strip()[:150],
        descricao=descricao.strip(),
        categoria=categoria,
        prioridade=prioridade,
        aberto_por=aberto_por,
        aluno=aluno,
    )


def responder(
    *, chamado: ChamadoDeSuporte, texto: str, autor=None, interna: bool = False
) -> MensagemDoChamado:
    if not (texto or "").strip():
        raise ErroDeConta("Escreva a resposta.")
    if not chamado.esta_aberto:
        raise ErroDeConta("Chamado fechado nao recebe mensagem; reabra antes de responder.")
    mensagem = MensagemDoChamado.objects.create(
        chamado=chamado, autor=autor, texto=texto.strip(), interna=interna
    )
    if chamado.situacao == ChamadoDeSuporte.Situacao.ABERTO:
        chamado.situacao = ChamadoDeSuporte.Situacao.EM_ANDAMENTO
        chamado.responsavel = chamado.responsavel or autor
        chamado.save(update_fields=["situacao", "responsavel"])
    return mensagem


def mudar_situacao(
    *, chamado: ChamadoDeSuporte, situacao: str, responsavel=None
) -> ChamadoDeSuporte:
    if situacao not in dict(ChamadoDeSuporte.Situacao.choices):
        raise ErroDeConta("Situacao de chamado desconhecida.")
    chamado.situacao = situacao
    if responsavel is not None and chamado.responsavel is None:
        chamado.responsavel = responsavel
    if situacao in {ChamadoDeSuporte.Situacao.RESOLVIDO, ChamadoDeSuporte.Situacao.FECHADO}:
        chamado.resolvido_em = timezone.now()
    chamado.save(update_fields=["situacao", "responsavel", "resolvido_em"])
    return chamado


def fila_do_suporte(rede, limite: int = 50):
    """Chamados abertos, do mais urgente para o mais antigo."""
    return (
        ChamadoDeSuporte.objects.filter(rede=rede)
        .exclude(
            situacao__in=[ChamadoDeSuporte.Situacao.RESOLVIDO, ChamadoDeSuporte.Situacao.FECHADO]
        )
        .select_related("unidade", "aberto_por", "aluno")
        .order_by("criado_em")[:limite]
    )


def resumo_do_suporte(rede) -> dict:
    chamados = ChamadoDeSuporte.objects.filter(rede=rede)
    abertos = chamados.exclude(
        situacao__in=[ChamadoDeSuporte.Situacao.RESOLVIDO, ChamadoDeSuporte.Situacao.FECHADO]
    )
    resolvidos = chamados.filter(resolvido_em__isnull=False)
    tempos = [
        (chamado.resolvido_em - chamado.criado_em).total_seconds() / 3600
        for chamado in resolvidos
        if chamado.resolvido_em and chamado.criado_em
    ]
    return {
        "total": chamados.count(),
        "abertos": abertos.count(),
        "urgentes": abertos.filter(prioridade=ChamadoDeSuporte.Prioridade.URGENTE).count(),
        "resolvidos": resolvidos.count(),
        "horas_medias": round(sum(tempos) / len(tempos), 1) if tempos else None,
    }


# ------------------------------------------------------------------ sessoes ativas
def sessoes_ativas(usuario, chave_atual: str = "") -> list[dict]:
    """Sessoes validas deste usuario — e qual delas e a que ele esta usando agora."""
    linhas = []
    for sessao in Session.objects.filter(expire_date__gte=timezone.now()).order_by("-expire_date"):
        dados = sessao.get_decoded()
        if str(dados.get("_auth_user_id")) != str(usuario.pk):
            continue
        linhas.append(
            {
                "chave": sessao.session_key,
                "expira_em": sessao.expire_date,
                "atual": sessao.session_key == chave_atual,
            }
        )
    return linhas


def encerrar_outras_sessoes(usuario, chave_atual: str = "") -> int:
    """Sai dos outros dispositivos, mantendo a sessao atual aberta."""
    removidas = 0
    for sessao in Session.objects.filter(expire_date__gte=timezone.now()):
        dados = sessao.get_decoded()
        if str(dados.get("_auth_user_id")) != str(usuario.pk):
            continue
        if sessao.session_key == chave_atual:
            continue
        sessao.delete()
        removidas += 1
    return removidas
