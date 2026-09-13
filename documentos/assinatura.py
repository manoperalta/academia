"""Assinatura eletronica simples, com trilha verificavel.

Cada assinatura entra numa **corrente de hashes**: a primeira aponta para o hash do documento, e cada
seguinte aponta para o hash da anterior. Verificar o envelope e refazer a conta e comparar — se
alguem trocar o arquivo depois de assinado, a verificacao acusa.

Assinatura com certificado ICP-Brasil fica pendente (exige certificado e contrato com a AC); o que
existe aqui e assinatura eletronica simples, que e o que a maioria dos contratos de academia usa.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path as Caminho
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from documentos.models import Assinatura, EnvelopeDeAssinatura, Signatario


class ErroDeAssinatura(Exception):
    """Falha esperada no fluxo de assinatura."""


def _resumo(*partes: object) -> str:
    return hashlib.sha256("|".join(str(parte) for parte in partes).encode()).hexdigest()


def _raiz() -> Caminho:
    return Caminho(settings.MEDIA_ROOT) / "redes"


def criar_envelope(
    *,
    rede,
    titulo: str,
    tipo: str = EnvelopeDeAssinatura.Tipo.CONTRATO,
    aluno=None,
    criado_por=None,
    documento: bytes | None = None,
    signatarios: list[dict] | None = None,
) -> EnvelopeDeAssinatura:
    """Monta o envelope, guarda o documento e registra quem assina."""
    if not (titulo or "").strip():
        raise ErroDeAssinatura("Dê um titulo ao envelope.")
    if tipo not in dict(EnvelopeDeAssinatura.Tipo.choices):
        raise ErroDeAssinatura("Tipo de documento desconhecido.")
    if documento is None:
        if aluno is None:
            raise ErroDeAssinatura("Sem aluno, e preciso enviar o documento.")
        from documentos import servicos as documentos_servicos

        documento = documentos_servicos.contrato_de_adesao(aluno.user)
    destino = _raiz() / rede.slug / "documentos" / f"{uuid4().hex}.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(documento)
    envelope = EnvelopeDeAssinatura.objects.create(
        rede=rede,
        aluno=aluno,
        tipo=tipo,
        titulo=titulo.strip(),
        caminho_do_documento=str(destino.relative_to(Caminho(settings.MEDIA_ROOT))),
        hash_do_documento=hashlib.sha256(documento).hexdigest(),
        criado_por=criado_por,
    )
    if not signatarios:
        signatarios = []
        if aluno is not None:
            signatarios.append(
                {
                    "nome": aluno.nome,
                    "papel": Signatario.Papel.ALUNO,
                    "email": getattr(aluno.user, "email", ""),
                }
            )
        nome_rede = getattr(rede, "nome", "academia")
        signatarios.append(
            {"nome": f"Representante de {nome_rede}", "papel": Signatario.Papel.ACADEMIA}
        )
    for posicao, dados in enumerate(signatarios, start=1):
        Signatario.objects.create(
            envelope=envelope,
            nome=dados.get("nome", ""),
            papel=dados.get("papel", "aluno"),
            email=dados.get("email", ""),
            ordem=dados.get("ordem") or posicao,
        )
    return envelope


def proximo_signatario(envelope: EnvelopeDeAssinatura) -> Signatario | None:
    return envelope.pendentes.order_by("ordem", "pk").first()


def assinar(*, signatario: Signatario, ip: str = "", navegador: str = "") -> Assinatura:
    """Assina, na ordem combinada, encadeando o hash da assinatura anterior."""
    envelope = signatario.envelope
    if signatario.situacao != Signatario.Situacao.PENDENTE:
        raise ErroDeAssinatura("Este signatario ja assinou ou recusou.")
    esperado = proximo_signatario(envelope)
    if esperado is not None and esperado.pk != signatario.pk:
        raise ErroDeAssinatura(
            f"A ordem combinada pede a assinatura de {esperado.nome} antes desta."
        )
    anterior = (
        Assinatura.objects.filter(signatario__envelope=envelope).order_by("-criado_em").first()
    )
    hash_anterior = anterior.hash_da_assinatura if anterior else envelope.hash_do_documento
    momento = timezone.now()
    # o carimbo entra no hash truncado ao segundo: o banco nao devolve microssegundos identicos,
    # e a conferencia precisa reproduzir exatamente o mesmo texto
    hash_da_assinatura = _resumo(
        envelope.hash_do_documento,
        hash_anterior,
        signatario.pk,
        signatario.nome,
        signatario.papel,
        momento.replace(microsecond=0).isoformat(),
    )
    assinatura = Assinatura.objects.create(
        signatario=signatario,
        hash_do_documento=envelope.hash_do_documento,
        hash_anterior=hash_anterior,
        hash_da_assinatura=hash_da_assinatura,
        endereco_ip=ip,
        navegador=navegador[:200],
    )
    signatario.situacao = Signatario.Situacao.ASSINOU
    signatario.assinou_em = momento
    signatario.save(update_fields=["situacao", "assinou_em"])
    _atualizar_situacao(envelope)
    return assinatura


def recusar(*, signatario: Signatario, motivo: str) -> Signatario:
    if not (motivo or "").strip():
        raise ErroDeAssinatura("Informe o motivo da recusa.")
    if signatario.situacao != Signatario.Situacao.PENDENTE:
        raise ErroDeAssinatura("Este signatario ja assinou ou recusou.")
    signatario.situacao = Signatario.Situacao.RECUSOU
    signatario.motivo_da_recusa = motivo.strip()[:200]
    signatario.save(update_fields=["situacao", "motivo_da_recusa"])
    envelope = signatario.envelope
    envelope.situacao = EnvelopeDeAssinatura.Situacao.RECUSADO
    envelope.save(update_fields=["situacao"])
    return signatario


def _atualizar_situacao(envelope: EnvelopeDeAssinatura) -> EnvelopeDeAssinatura:
    pendentes = envelope.pendentes.count()
    assinados = envelope.assinaturas_ok
    if pendentes == 0 and assinados:
        envelope.situacao = EnvelopeDeAssinatura.Situacao.ASSINADO
        envelope.concluido_em = timezone.now()
        envelope.save(update_fields=["situacao", "concluido_em"])
    elif assinados:
        envelope.situacao = EnvelopeDeAssinatura.Situacao.PARCIAL
        envelope.save(update_fields=["situacao"])
    return envelope


def verificar(envelope: EnvelopeDeAssinatura) -> dict:
    """Refaz a corrente e confere o documento: e assim que se prova que nada mudou depois."""
    divergencias: list[str] = []
    caminho = Caminho(settings.MEDIA_ROOT) / envelope.caminho_do_documento
    if not caminho.is_file():
        divergencias.append("O arquivo do documento nao esta mais no armazenamento.")
    else:
        atual = hashlib.sha256(caminho.read_bytes()).hexdigest()
        if atual != envelope.hash_do_documento:
            divergencias.append("O documento foi alterado depois do registro do envelope.")
    anterior = envelope.hash_do_documento
    for assinatura in (
        Assinatura.objects.filter(signatario__envelope=envelope)
        .select_related("signatario")
        .order_by("criado_em")
    ):
        if assinatura.hash_anterior != anterior:
            divergencias.append(
                f"A corrente quebrou na assinatura de {assinatura.signatario.nome}."
            )
        carimbo = assinatura.criado_em.replace(microsecond=0).isoformat()
        esperado = _resumo(
            assinatura.hash_do_documento,
            assinatura.hash_anterior,
            assinatura.signatario.pk,
            assinatura.signatario.nome,
            assinatura.signatario.papel,
            carimbo,
        )
        if esperado != assinatura.hash_da_assinatura:
            divergencias.append(
                f"O hash da assinatura de {assinatura.signatario.nome} nao confere."
            )
        anterior = assinatura.hash_da_assinatura
    return {
        "ok": not divergencias,
        "divergencias": divergencias,
        "assinaturas": Assinatura.objects.filter(signatario__envelope=envelope).count(),
        "conferido_em": timezone.now(),
    }


def termo_de_assinaturas(envelope: EnvelopeDeAssinatura) -> bytes:
    """Folha de assinaturas em PDF: quem assinou, quando e com qual hash."""
    from documentos.pdf import DocumentoPDF

    documento = DocumentoPDF(
        titulo="Termo de assinaturas",
        subtitulo=f"{envelope.titulo} — {envelope.rede.nome}",
        rodape=f"{envelope.rede.nome} — documento gerado pelo SafeStack Academia",
    )
    documento.secao("Documento")
    documento.par("Tipo", envelope.get_tipo_display())
    documento.par("Situacao", envelope.get_situacao_display())
    documento.par("Aluno", getattr(envelope.aluno, "nome", "") or "—")
    documento.par("Hash do documento", envelope.hash_do_documento)
    documento.secao("Assinaturas")
    linhas = []
    for signatario in envelope.signatarios.order_by("ordem", "pk"):
        assinatura = getattr(signatario, "assinatura", None)
        linhas.append(
            [
                signatario.nome,
                signatario.get_papel_display(),
                signatario.assinou_em.strftime("%d/%m/%Y %H:%M") if signatario.assinou_em else "—",
                (assinatura.hash_da_assinatura[:16] + "…") if assinatura else "—",
            ]
        )
    documento.tabela(
        [
            ("Nome", 2.4, "esquerda"),
            ("Papel", 1.4, "esquerda"),
            ("Quando", 1.4, "esquerda"),
            ("Hash", 1.6, "esquerda"),
        ],
        linhas,
    )
    conferencia = verificar(envelope)
    documento.secao("Conferencia")
    documento.par("Situacao da corrente", "integral" if conferencia["ok"] else "DIVERGENTE")
    for divergencia in conferencia["divergencias"]:
        documento.texto(f"- {divergencia}", tamanho=9, cor=(0.5, 0.2, 0.2))
    documento.espaco(8)
    documento.texto(
        "Assinatura eletronica simples com trilha de auditoria. Assinatura com "
        "certificado ICP-Brasil fica pendente de certificado e contratacao da AC.",
        tamanho=8.5,
        cor=(0.4, 0.4, 0.4),
    )
    return documento.salvar()


def resumo_das_assinaturas(rede) -> dict:
    envelopes = EnvelopeDeAssinatura.objects.filter(rede=rede)
    return {
        "total": envelopes.count(),
        "assinados": envelopes.filter(situacao=EnvelopeDeAssinatura.Situacao.ASSINADO).count(),
        "aguardando": envelopes.filter(
            situacao__in=[
                EnvelopeDeAssinatura.Situacao.AGUARDANDO,
                EnvelopeDeAssinatura.Situacao.PARCIAL,
            ]
        ).count(),
        "recusados": envelopes.filter(situacao=EnvelopeDeAssinatura.Situacao.RECUSADO).count(),
        "pendentes_de_assinatura": Signatario.objects.filter(
            envelope__rede=rede, situacao=Signatario.Situacao.PENDENTE
        ).count(),
        "valor_decimal_exemplo": Decimal("0.00"),
    }
