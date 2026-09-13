"""Calculo de NPS e ciclo de tratamento do detrator."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from nps.models import Pesquisa, Resposta, TipoDePesquisa


class ErroDePesquisa(Exception):
    """Operacao recusada."""


def registrar_resposta(
    pesquisa: Pesquisa, aluno=None, nota: int | None = None, comentario: str = ""
) -> Resposta:
    """Uma resposta por aluno; nota obrigatoria para NPS/nota (0-10 / 1-5)."""
    if not pesquisa.aceita_resposta():
        raise ErroDePesquisa("pesquisa fora do periodo de respostas")
    if pesquisa.tipo == TipoDePesquisa.TEXTO:
        if not (comentario or "").strip():
            raise ErroDePesquisa("escreva o comentario")
    else:
        if nota is None:
            raise ErroDePesquisa("informe a nota")
        maximo = 10 if pesquisa.tipo == TipoDePesquisa.NPS else 5
        if not 0 <= int(nota) <= maximo:
            raise ErroDePesquisa(f"a nota deve ficar entre 0 e {maximo}")
    if aluno is not None and Resposta.objects.filter(pesquisa=pesquisa, aluno=aluno).exists():
        raise ErroDePesquisa("este aluno ja respondeu esta pesquisa")
    resposta = Resposta.objects.create(
        pesquisa=pesquisa,
        aluno=aluno,
        unidade=getattr(aluno, "unidade", None) or pesquisa.unidade,
        nota=None if pesquisa.tipo == TipoDePesquisa.TEXTO else nota,
        comentario=comentario or "",
    )
    if aluno is not None:
        from gamificacao.servicos import pontuar

        pontuar(aluno, "nps", referencia=f"pesquisa-{pesquisa.pk}")
    return resposta


def nps(pesquisa: Pesquisa | None = None, unidade=None, inicio=None, fim=None) -> dict:
    """NPS = %promotores - %detratores (9-10 promovem, 7-8 sao neutros, 0-6 detratam)."""
    consulta = Resposta.objects.exclude(nota__isnull=True)
    if pesquisa is not None:
        consulta = consulta.filter(pesquisa=pesquisa)
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    if inicio is not None:
        consulta = consulta.filter(criado_em__date__gte=inicio)
    if fim is not None:
        consulta = consulta.filter(criado_em__date__lte=fim)
    notas = list(consulta.values_list("nota", flat=True))
    total = len(notas)
    if not total:
        return {
            "respostas": 0,
            "promotores": 0,
            "neutros": 0,
            "detratores": 0,
            "nps": None,
            "media": None,
            "classificacao": "sem respostas",
        }
    promotores = sum(1 for nota in notas if nota >= 9)
    neutros = sum(1 for nota in notas if 7 <= nota <= 8)
    detratores = sum(1 for nota in notas if nota <= 6)
    valor = Decimal(promotores * 100 - detratores * 100) / Decimal(total)
    nps_valor = int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    media = round(sum(notas) / total, 2)
    faixa = (
        "excelente"
        if nps_valor >= 75
        else "muito bom"
        if nps_valor >= 50
        else "razoavel"
        if nps_valor >= 0
        else "critico"
    )
    return {
        "respostas": total,
        "promotores": promotores,
        "neutros": neutros,
        "detratores": detratores,
        "nps": nps_valor,
        "media": media,
        "classificacao": faixa,
        "percentual_promotores": round(promotores * 100 / total, 1),
        "percentual_detratores": round(detratores * 100 / total, 1),
    }


def detratores_para_tratar(rede=None, unidade=None, limite: int = 50):
    """Fila de recuperacao: quem deu nota baixa e ainda nao foi contatado."""
    consulta = Resposta.objects.filter(
        nota__lte=6, tratada_em__isnull=True, pesquisa__tipo=TipoDePesquisa.NPS
    ).select_related("aluno", "unidade", "pesquisa")
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    elif rede is not None:
        consulta = consulta.filter(pesquisa__rede=rede)
    return consulta[:limite]


def marcar_tratada(resposta: Resposta, usuario=None, observacao: str = "") -> Resposta:
    resposta.tratada_em = timezone.now()
    resposta.tratada_por = usuario if getattr(usuario, "pk", None) else None
    if observacao:
        resposta.comentario = f"{resposta.comentario}\n[tratativa] {observacao}".strip()
    resposta.save(update_fields=["tratada_em", "tratada_por", "comentario"])
    return resposta


def resumo_por_unidade(rede, inicio=None, fim=None) -> list[dict]:
    """NPS lado a lado por unidade — o que a rede usa para achar a unidade fraca."""
    from core.models import Unidade

    linhas = []
    for unidade in Unidade.objects.filter(rede=rede):
        linhas.append({"unidade": unidade, **nps(unidade=unidade, inicio=inicio, fim=fim)})
    return sorted(linhas, key=lambda item: (item["nps"] is None, -(item["nps"] or 0)))
