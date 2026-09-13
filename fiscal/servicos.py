"""Servicos fiscais: calculo dos tributos, emissao, cancelamento e PDF da nota.

O calculo fica **explicito e guardado** na nota (base, aliquota, ISS e cada retencao), como no
repasse: quando o contador perguntar de onde saiu o valor, a resposta esta no proprio registro.

**Emissao em modo simulado** enquanto nao houver provedor integrado — declarado na tela, no PDF e na
resposta guardada. Nota fiscal de cliente nao se inventa.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from fiscal.models import ConfiguracaoFiscal, EventoFiscal, NotaFiscal

CENTAVO = Decimal("0.01")
#: Retencoes federais aplicaveis a servicos (percentuais de referencia).
RETENCOES = {
    "pis": (Decimal("0.65"), "PIS"),
    "cofins": (Decimal("3.00"), "COFINS"),
    "csll": (Decimal("1.00"), "CSLL"),
    "ir": (Decimal("1.50"), "IR"),
    "inss": (Decimal("11.00"), "INSS"),
}


class ErroFiscal(Exception):
    """Falha esperada no fluxo fiscal."""


def _arredondar(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def configurar_fiscal(*, rede, **campos) -> ConfiguracaoFiscal:
    """Cria ou atualiza a configuracao fiscal da rede, validando o que muda o valor da nota."""
    aliquota = Decimal(str(campos.get("aliquota_iss", 0) or 0))
    if aliquota < 0 or aliquota > 20:
        raise ErroFiscal("Aliquota de ISS fora de faixa (0 a 20%).")
    try:
        codigo = int(str(campos.get("codigo_do_servico", "6.01")).replace(".", ""))
    except (TypeError, ValueError) as erro:
        raise ErroFiscal("Codigo de servico invalido (padrao 6.01).") from erro
    if codigo <= 0:
        raise ErroFiscal("Codigo de servico invalido (padrao 6.01).")
    configuracao, _criada = ConfiguracaoFiscal.objects.update_or_create(
        rede=rede,
        defaults={**campos, "aliquota_iss": aliquota},
    )
    return configuracao


def calcular_tributos(valor, configuracao: ConfiguracaoFiscal) -> dict:
    """Memoria de calculo dos tributos sobre o valor do servico."""
    base = _arredondar(Decimal(str(valor or 0)))
    aliquota = Decimal(str(configuracao.aliquota_iss or 0))
    iss = _arredondar(base * aliquota / 100)
    retencoes: dict[str, str] = {}
    for chave, (percentual, _rotulo) in RETENCOES.items():
        if chave == "inss" and not configuracao.retem_inss:
            continue
        if chave == "ir" and not configuracao.retem_ir:
            continue
        if chave in {"pis", "cofins", "csll"} and not configuracao.retem_pis_cofins_csll:
            continue
        retencoes[chave] = str(_arredondar(base * percentual / 100))
    total_retencoes = sum((Decimal(valor_) for valor_ in retencoes.values()), Decimal("0"))
    return {
        "base_de_calculo": base,
        "aliquota_iss": aliquota,
        "valor_do_iss": iss,
        "retencoes": retencoes,
        "valor_liquido": _arredondar(base - total_retencoes),
        "memoria": [
            f"Valor do servico: R$ {base}",
            f"ISS {aliquota}% sobre R$ {base}: R$ {iss}",
            *[
                f"{RETENCOES[chave][1]} {RETENCOES[chave][0]}%: R$ {valor_}"
                for chave, valor_ in retencoes.items()
            ],
            f"Liquido a receber: R$ {_arredondar(base - total_retencoes)}",
        ],
    }


def _aluno_do_pagamento(pagamento):
    """O tomador e o perfil de aluno; ``Pagamento.usuario`` guarda o login."""
    from usuarios.models import Usuario

    if pagamento is None or pagamento.usuario is None:
        return None
    return Usuario.todos.filter(rede=pagamento.rede, user=pagamento.usuario).first()


def _configuracao(rede) -> ConfiguracaoFiscal:
    configuracao = ConfiguracaoFiscal.objects.filter(rede=rede).first()
    if configuracao is None:
        raise ErroFiscal("Configure os dados fiscais da rede antes de emitir nota.")
    return configuracao


def _proximo_numero(configuracao: ConfiguracaoFiscal) -> str:
    ultima = (
        NotaFiscal.objects.filter(rede=configuracao.rede, serie=configuracao.serie)
        .exclude(numero="")
        .order_by("-id")
        .first()
    )
    if ultima is None or not ultima.numero.isdigit():
        return "1"
    return str(int(ultima.numero) + 1)


def emitir_nota(
    *,
    rede,
    valor,
    competencia: date | None = None,
    aluno=None,
    unidade=None,
    pagamento=None,
    descricao: str = "",
    emitida_por=None,
) -> NotaFiscal:
    """Monta a nota com a conta dos tributos e transmite (simulado, sem provedor integrado)."""
    configuracao = _configuracao(rede)
    if pagamento is not None and NotaFiscal.objects.filter(pagamento=pagamento).exists():
        raise ErroFiscal("Este pagamento ja tem nota fiscal.")
    conta = calcular_tributos(valor, configuracao)
    if conta["base_de_calculo"] <= 0:
        raise ErroFiscal("Valor do servico precisa ser maior que zero.")
    nota = NotaFiscal.objects.create(
        rede=rede,
        unidade=unidade or getattr(aluno, "unidade", None),
        aluno=aluno,
        pagamento=pagamento,
        competencia=competencia or timezone.localdate().replace(day=1),
        descricao_do_servico=descricao or "Mensalidade de atividade fisica",
        codigo_do_servico=configuracao.codigo_do_servico,
        valor_do_servico=conta["base_de_calculo"],
        base_de_calculo=conta["base_de_calculo"],
        aliquota_iss=conta["aliquota_iss"],
        valor_do_iss=conta["valor_do_iss"],
        retencoes=conta["retencoes"],
        valor_liquido=conta["valor_liquido"],
    )
    EventoFiscal.objects.create(
        nota=nota, tipo=EventoFiscal.Tipo.CRIADA, detalhe="; ".join(conta["memoria"])
    )
    return _transmitir(nota, configuracao, emitida_por=emitida_por)


def _transmitir(nota: NotaFiscal, configuracao: ConfiguracaoFiscal, emitida_por=None) -> NotaFiscal:
    if configuracao.provedor != ConfiguracaoFiscal.Provedor.SIMULADO:
        nota.situacao = NotaFiscal.Situacao.ERRO
        nota.save(update_fields=["situacao"])
        EventoFiscal.objects.create(
            nota=nota,
            tipo=EventoFiscal.Tipo.ERRO,
            detalhe=f"Provedor '{configuracao.get_provedor_display()}' ainda nao integrado; "
            f"a nota ficou registrada sem transmissao.",
        )
        return nota
    numero = _proximo_numero(configuracao)
    codigo = hashlib.sha256(
        f"{configuracao.rede.slug}|{configuracao.serie}|{numero}|{nota.valor_do_servico}|"
        f"{nota.competencia:%Y%m}".encode()
    ).hexdigest()[:32]
    nota.numero = numero
    nota.serie = configuracao.serie
    nota.codigo_de_verificacao = codigo
    nota.provedor = configuracao.provedor
    nota.situacao = NotaFiscal.Situacao.EMITIDA
    nota.emitida_em = timezone.now()
    nota.resposta_do_provedor = {
        "modo": "simulado",
        "aviso": "Emissao simulada: nenhuma nota foi transmitida ao municipio.",
        "numero": numero,
        "serie": configuracao.serie,
        "codigo_de_verificacao": codigo,
    }
    nota.save(
        update_fields=[
            "numero",
            "serie",
            "codigo_de_verificacao",
            "provedor",
            "situacao",
            "emitida_em",
            "resposta_do_provedor",
        ]
    )
    EventoFiscal.objects.create(
        nota=nota,
        tipo=EventoFiscal.Tipo.EMITIDA,
        detalhe=f"Nota {numero}/{configuracao.serie} emitida em modo simulado.",
        dados={"codigo_de_verificacao": codigo},
    )
    return nota


def cancelar_nota(nota: NotaFiscal, motivo: str) -> NotaFiscal:
    if not (motivo or "").strip():
        raise ErroFiscal("O cancelamento exige motivo (a fiscalizacao pede justificativa).")
    if nota.situacao == NotaFiscal.Situacao.CANCELADA:
        raise ErroFiscal("Esta nota ja esta cancelada.")
    if nota.situacao != NotaFiscal.Situacao.EMITIDA:
        raise ErroFiscal("So nota emitida pode ser cancelada.")
    nota.situacao = NotaFiscal.Situacao.CANCELADA
    nota.cancelada_em = timezone.now()
    nota.motivo_do_cancelamento = motivo.strip()[:200]
    nota.save(update_fields=["situacao", "cancelada_em", "motivo_do_cancelamento"])
    EventoFiscal.objects.create(
        nota=nota, tipo=EventoFiscal.Tipo.CANCELADA, detalhe=nota.motivo_do_cancelamento
    )
    return nota


def emitir_notas_da_competencia(rede, competencia: date, dry_run: bool = False) -> dict:
    """Emite a nota de cada mensalidade paga na competencia (idempotente por pagamento)."""
    from financeiro.models import Pagamento

    competencia = competencia.replace(day=1)
    fim = (competencia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    pagamentos = Pagamento.todos.filter(
        rede=rede, status="pago", data_inicio__gte=competencia, data_inicio__lte=fim
    ).select_related("usuario", "unidade")
    emitidas, puladas = [], []
    for pagamento in pagamentos:
        if NotaFiscal.objects.filter(pagamento=pagamento).exists():
            puladas.append(pagamento.pk)
            continue
        emitidas.append(
            {
                "pagamento": pagamento.pk,
                "aluno": str(pagamento.usuario),
                "valor": str(pagamento.valor_pago),
            }
        )
        if dry_run:
            continue
        emitir_nota(
            rede=rede,
            valor=pagamento.valor_pago,
            competencia=pagamento.data_inicio or competencia,
            aluno=_aluno_do_pagamento(pagamento),
            unidade=pagamento.unidade,
            pagamento=pagamento,
        )
    return {
        "competencia": competencia,
        "dry_run": dry_run,
        "emitidas": emitidas,
        "ja_tinham_nota": puladas,
        "total_de_pagamentos": pagamentos.count(),
    }


def resumo_fiscal(rede, competencia: date | None = None) -> dict:
    competencia = (competencia or timezone.localdate()).replace(day=1)
    fim = (competencia + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    notas = NotaFiscal.objects.filter(rede=rede, competencia__gte=competencia, competencia__lte=fim)
    emitidas = notas.filter(situacao=NotaFiscal.Situacao.EMITIDA)
    faturado = sum((nota.valor_do_servico for nota in emitidas), Decimal("0"))
    iss = sum((nota.valor_do_iss for nota in emitidas), Decimal("0"))
    retido = sum((nota.total_retencoes for nota in emitidas), Decimal("0"))
    return {
        "competencia": competencia,
        "notas": notas.count(),
        "emitidas": emitidas.count(),
        "canceladas": notas.filter(situacao=NotaFiscal.Situacao.CANCELADA).count(),
        "com_erro": notas.filter(situacao=NotaFiscal.Situacao.ERRO).count(),
        "valor_faturado": faturado,
        "valor_do_iss": iss,
        "valor_retido": retido,
        "liquido": faturado - retido,
        "sem_nota": _pagamentos_sem_nota(rede, competencia, fim),
    }


def _pagamentos_sem_nota(rede, competencia, fim) -> int:
    from financeiro.models import Pagamento

    return Pagamento.todos.filter(
        rede=rede,
        status="pago",
        data_inicio__gte=competencia,
        data_inicio__lte=fim,
        notas_fiscais__isnull=True,
    ).count()


def pdf_da_nota(nota: NotaFiscal) -> bytes:
    """Nota em PDF, no gerador proprio do projeto (sem dependencia externa)."""
    from documentos.pdf import DocumentoPDF, moeda

    configuracao = ConfiguracaoFiscal.objects.filter(rede=nota.rede).first()
    emitente = nota.rede.nome
    documento = DocumentoPDF(
        titulo=f"Nota de servico {nota.numero or '(sem numero)'}/{nota.serie or '-'}",
        subtitulo=f"{emitente}"
        + (
            f" - inscricao municipal {configuracao.inscricao_municipal}"
            if configuracao and configuracao.inscricao_municipal
            else ""
        ),
        rodape=f"{emitente} - documento gerado pelo SafeStack Academia",
    )
    documento.secao("Prestador")
    documento.par("Razao social", nota.rede.nome)
    documento.par("Regime", configuracao.get_regime_display() if configuracao else "")
    documento.par("Municipio", configuracao.municipio if configuracao else "")
    documento.par("Competencia", f"{nota.competencia:%m/%Y}")
    documento.secao("Tomador")
    documento.par("Nome", getattr(nota.aluno, "nome", "") or "consumidor")
    documento.par("Unidade", getattr(nota.unidade, "nome", ""))
    documento.secao("Servico")
    documento.par("Descricao", nota.descricao_do_servico)
    documento.par("Codigo do servico (LC 116)", nota.codigo_do_servico)
    documento.secao("Valores")
    documento.tabela(
        [("Linha", 3, "esquerda"), ("Valor", 1.2, "direita")],
        [
            ["Valor do servico", moeda(nota.valor_do_servico)],
            [f"ISS ({nota.aliquota_iss}%)", moeda(nota.valor_do_iss)],
            *[
                [f"Retencao {chave.upper()}", moeda(valor)]
                for chave, valor in (nota.retencoes or {}).items()
            ],
            ["Liquido a receber", moeda(nota.valor_liquido)],
        ],
    )
    documento.secao("Situacao")
    documento.par("Situacao", nota.get_situacao_display())
    documento.par(
        "Emitida em", nota.emitida_em.strftime("%d/%m/%Y %H:%M") if nota.emitida_em else ""
    )
    documento.par("Codigo de verificacao", nota.codigo_de_verificacao)
    if nota.motivo_do_cancelamento:
        documento.par("Cancelada", nota.motivo_do_cancelamento)
    aviso = (nota.resposta_do_provedor or {}).get("aviso", "")
    if aviso:
        documento.espaco(8)
        documento.texto(aviso, tamanho=9, cor=(0.5, 0.2, 0.2))
    documento.espaco(6)
    documento.texto(
        "Documento de conferencia interna. A nota fiscal oficial e a emitida no "
        "sistema do municipio.",
        tamanho=8.5,
        cor=(0.4, 0.4, 0.4),
    )
    return documento.salvar()
