"""Servicos de relacionamento: funil de captacao e risco de evasao explicado.

O score de risco e montado como uma **memoria de calculo**: cada sinal soma (ou subtrai) pontos e a
lista ``motivos`` registra a conta, para a equipe discutir o caso em vez de confiar num numero solto.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from relacionamento.models import (
    InteracaoComLead,
    Lead,
    OrigemDoLead,
    PerfilDeRisco,
)

#: Pesos do risco. Mexer aqui muda a conta em todo lugar — de proposito.
PESO_SEM_TREINAR_30 = 35
PESO_SEM_TREINAR_14 = 20
PESO_SEM_TREINAR_7 = 10
PESO_ATRASO_30 = 30
PESO_ATRASO_7 = 20
PESO_ATRASO_QUALQUER = 10
PESO_SEM_PAGAMENTO = 15
PESO_DETRATOR = 20
PESO_NOVATO = 10
PESO_SEM_PLANO_VIGENTE = 10
REDUCAO_TREINOU_NA_SEMANA = 15
REDUCAO_FREQUENTE = 10


class ErroDeRelacionamento(Exception):
    """Falha esperada no fluxo de CRM ou de retencao."""


# ------------------------------------------------------------------ captacao
def registrar_lead(
    *,
    rede,
    nome: str,
    origem: str = OrigemDoLead.OUTRO,
    telefone: str = "",
    email: str = "",
    interesse: str = "",
    unidade=None,
    responsavel=None,
    valor_estimado=Decimal("0"),
    observacoes: str = "",
) -> Lead:
    """Cria o lead; se ja houver um lead aberto com o mesmo telefone, reaproveita o registro."""
    if not (nome or "").strip():
        raise ErroDeRelacionamento("Informe o nome do interessado.")
    if origem not in dict(OrigemDoLead.choices):
        raise ErroDeRelacionamento("Origem desconhecida.")
    telefone_limpo = "".join(caractere for caractere in (telefone or "") if caractere.isdigit())
    if telefone_limpo:
        existente = (
            Lead.objects.filter(rede=rede, telefone=telefone_limpo)
            .exclude(situacao__in=[Lead.Situacao.MATRICULADO, Lead.Situacao.PERDIDO])
            .first()
        )
        if existente is not None:
            return existente
    return Lead.objects.create(
        rede=rede,
        unidade=unidade,
        nome=nome.strip(),
        telefone=telefone_limpo,
        email=email,
        origem=origem,
        interesse=interesse,
        valor_estimado=valor_estimado,
        responsavel=responsavel,
        observacoes=observacoes,
    )


def registrar_interacao(
    *,
    lead: Lead,
    tipo: str,
    resumo: str,
    feito_por=None,
    resultado: str = "",
    proximo_contato_em=None,
) -> InteracaoComLead:
    """Registra o contato e avanca o funil conforme o que aconteceu."""
    if not (resumo or "").strip():
        raise ErroDeRelacionamento("Descreva o que foi conversado.")
    if tipo not in dict(InteracaoComLead.Tipo.choices):
        raise ErroDeRelacionamento("Tipo de contato desconhecido.")
    interacao = InteracaoComLead.objects.create(
        lead=lead,
        tipo=tipo,
        resumo=resumo.strip(),
        resultado=resultado,
        feito_por=feito_por,
        proximo_contato_em=proximo_contato_em,
    )
    mudancas = []
    if lead.situacao == Lead.Situacao.NOVO:
        lead.situacao = Lead.Situacao.CONTATADO
        mudancas.append("situacao")
    if tipo == InteracaoComLead.Tipo.VISITA and lead.situacao in {
        Lead.Situacao.NOVO,
        Lead.Situacao.CONTATADO,
        Lead.Situacao.VISITA_AGENDADA,
    }:
        lead.situacao = Lead.Situacao.VISITOU
        mudancas.append("situacao")
    if proximo_contato_em is not None:
        lead.proximo_contato_em = proximo_contato_em
        mudancas.append("proximo_contato_em")
    if mudancas:
        lead.save(update_fields=list(dict.fromkeys(mudancas)))
    return interacao


def agendar_visita(*, lead: Lead, quando, feito_por=None) -> Lead:
    if lead.situacao in {Lead.Situacao.MATRICULADO, Lead.Situacao.PERDIDO}:
        raise ErroDeRelacionamento("Este lead ja saiu do funil.")
    lead.situacao = Lead.Situacao.VISITA_AGENDADA
    lead.proximo_contato_em = quando
    lead.save(update_fields=["situacao", "proximo_contato_em"])
    return lead


def converter_lead(*, lead: Lead, aluno, plano=None) -> Lead:
    """Fecha o lead como matricula: guarda quem virou aluno e quando."""
    if lead.situacao == Lead.Situacao.MATRICULADO:
        raise ErroDeRelacionamento("Este lead ja foi convertido em aluno.")
    if lead.situacao == Lead.Situacao.PERDIDO:
        raise ErroDeRelacionamento("Lead marcado como perdido nao pode ser convertido.")
    lead.situacao = Lead.Situacao.MATRICULADO
    lead.aluno = aluno
    lead.convertido_em = timezone.now()
    lead.motivo_da_perda = ""
    if plano is not None and not lead.interesse:
        lead.interesse = getattr(plano, "nome", "") or ""
    lead.save(update_fields=["situacao", "aluno", "convertido_em", "motivo_da_perda", "interesse"])
    return lead


def marcar_perdido(*, lead: Lead, motivo: str) -> Lead:
    if not (motivo or "").strip():
        raise ErroDeRelacionamento("Informe o motivo da perda — e o que permite corrigir o canal.")
    lead.situacao = Lead.Situacao.PERDIDO
    lead.motivo_da_perda = motivo.strip()[:200]
    lead.save(update_fields=["situacao", "motivo_da_perda"])
    return lead


def funil(rede) -> dict:
    """Contagem por etapa e conversao por origem (quem traz aluno que fica)."""
    leads = Lead.objects.filter(rede=rede)
    por_situacao = {
        valor: leads.filter(situacao=valor).count() for valor, _rotulo in Lead.Situacao.choices
    }
    total = leads.count()
    convertidos = por_situacao[Lead.Situacao.MATRICULADO]
    origens = []
    for valor, rotulo in OrigemDoLead.choices:
        do_canal = leads.filter(origem=valor)
        quantidade = do_canal.count()
        if not quantidade:
            continue
        matriculados = do_canal.filter(situacao=Lead.Situacao.MATRICULADO).count()
        origens.append(
            {
                "origem": rotulo,
                "leads": quantidade,
                "matriculados": matriculados,
                "taxa": round(matriculados * 100 / quantidade, 1),
            }
        )
    origens.sort(key=lambda linha: (-linha["matriculados"], -linha["leads"]))
    dias = [
        lead.dias_ate_matricular
        for lead in leads.filter(situacao=Lead.Situacao.MATRICULADO, convertido_em__isnull=False)
    ]
    dias = [dia for dia in dias if dia is not None]
    return {
        "total": total,
        "por_situacao": por_situacao,
        "convertidos": convertidos,
        "taxa_de_conversao": round(convertidos * 100 / total, 1) if total else 0.0,
        "por_origem": origens,
        "dias_ate_matricular": round(sum(dias) / len(dias), 1) if dias else None,
        "abertos": leads.exclude(
            situacao__in=[Lead.Situacao.MATRICULADO, Lead.Situacao.PERDIDO]
        ).count(),
        "sem_responsavel": leads.filter(
            situacao__in=[Lead.Situacao.NOVO, Lead.Situacao.CONTATADO], responsavel__isnull=True
        ).count(),
    }


def leads_para_contato(rede, limite: int = 50):
    """Fila de trabalho: quem tem contato marcado para hoje ou ja atrasado."""
    hoje = timezone.localdate()
    return (
        Lead.objects.filter(rede=rede)
        .exclude(situacao__in=[Lead.Situacao.MATRICULADO, Lead.Situacao.PERDIDO])
        .filter(Q(proximo_contato_em__lte=hoje) | Q(proximo_contato_em__isnull=True))
        .select_related("unidade", "responsavel")
        .order_by("proximo_contato_em", "-criado_em")[:limite]
    )


# ------------------------------------------------------------------ retencao
def _dias_desde(data) -> int | None:
    if data is None:
        return None
    return (timezone.now() - data).days


def calcular_risco(aluno) -> dict:
    """Monta a conta do risco do aluno: cada sinal soma ou reduz, e a lista explica."""
    from area_do_aluno.models import CheckinDoAluno
    from financeiro.models import Pagamento
    from nps.models import Resposta

    hoje = timezone.localdate()
    motivos: list[str] = []
    pontuacao = 0

    checkins = CheckinDoAluno.objects.filter(aluno=aluno)
    total_de_checkins = checkins.count()
    ultimo = checkins.order_by("-criado_em").first()
    dias_sem_treinar = _dias_desde(ultimo.criado_em) if ultimo else None

    if dias_sem_treinar is None:
        pontuacao += PESO_SEM_TREINAR_30
        motivos.append(f"Nunca registrou check-in: +{PESO_SEM_TREINAR_30}")
    elif dias_sem_treinar > 30:
        pontuacao += PESO_SEM_TREINAR_30
        motivos.append(f"{dias_sem_treinar} dias sem treinar: +{PESO_SEM_TREINAR_30}")
    elif dias_sem_treinar > 14:
        pontuacao += PESO_SEM_TREINAR_14
        motivos.append(f"{dias_sem_treinar} dias sem treinar: +{PESO_SEM_TREINAR_14}")
    elif dias_sem_treinar > 7:
        pontuacao += PESO_SEM_TREINAR_7
        motivos.append(f"{dias_sem_treinar} dias sem treinar: +{PESO_SEM_TREINAR_7}")
    else:
        pontuacao -= REDUCAO_TREINOU_NA_SEMANA
        motivos.append(
            f"Treinou nos ultimos {dias_sem_treinar} dia(s): -{REDUCAO_TREINOU_NA_SEMANA}"
        )

    # Escopo explicito pela rede: o risco nao pode depender do contexto da requisicao.
    pagamentos = Pagamento.todos.filter(rede=aluno.rede, usuario=aluno.user)
    ultimo_pagamento = pagamentos.order_by("-data_fim", "-id").first()
    dias_em_atraso = None
    if ultimo_pagamento is None:
        pontuacao += PESO_SEM_PAGAMENTO
        motivos.append(f"Sem pagamento registrado: +{PESO_SEM_PAGAMENTO}")
    else:
        fim = ultimo_pagamento.data_fim
        atraso = (hoje - fim).days if fim and fim < hoje else 0
        if atraso > 0:
            dias_em_atraso = atraso
            if atraso > 30:
                pontuacao += PESO_ATRASO_30
                motivos.append(f"Mensalidade vencida ha {atraso} dias: +{PESO_ATRASO_30}")
            elif atraso > 7:
                pontuacao += PESO_ATRASO_7
                motivos.append(f"Mensalidade vencida ha {atraso} dias: +{PESO_ATRASO_7}")
            else:
                pontuacao += PESO_ATRASO_QUALQUER
                motivos.append(f"Mensalidade vencida ha {atraso} dia(s): +{PESO_ATRASO_QUALQUER}")
        if ultimo_pagamento.status != "pago":
            pontuacao += PESO_SEM_PLANO_VIGENTE
            motivos.append(
                f"Pagamento com situacao '{ultimo_pagamento.status}': +{PESO_SEM_PLANO_VIGENTE}"
            )

    detrator = Resposta.objects.filter(
        aluno=aluno, nota__lte=6, criado_em__gte=timezone.now() - timedelta(days=90)
    ).exists()
    if detrator:
        pontuacao += PESO_DETRATOR
        motivos.append(f"Avaliou a academia com nota de detrator: +{PESO_DETRATOR}")

    dias_de_casa = _dias_desde(getattr(aluno, "criado_em", None))
    if dias_de_casa is not None and dias_de_casa < 30:
        pontuacao += PESO_NOVATO
        motivos.append(f"Aluno novo ({dias_de_casa} dia(s) de casa): +{PESO_NOVATO}")

    if total_de_checkins >= 12:
        pontuacao -= REDUCAO_FREQUENTE
        motivos.append(f"Frequencia alta ({total_de_checkins} check-ins): -{REDUCAO_FREQUENTE}")

    pontuacao = max(0, min(100, pontuacao))
    if pontuacao >= 75:
        faixa = PerfilDeRisco.Faixa.CRITICO
        acao = PerfilDeRisco.Acao.OFERTA_RETENCAO
    elif pontuacao >= 50:
        faixa = PerfilDeRisco.Faixa.ALTO
        acao = PerfilDeRisco.Acao.CONTATO_WHATSAPP
    elif pontuacao >= 25:
        faixa = PerfilDeRisco.Faixa.MEDIO
        acao = PerfilDeRisco.Acao.CONVITE_AVALIACAO
    else:
        faixa = PerfilDeRisco.Faixa.BAIXO
        acao = PerfilDeRisco.Acao.NENHUMA
    return {
        "pontuacao": pontuacao,
        "faixa": faixa,
        "acao": acao,
        "motivos": motivos,
        "dias_sem_treinar": dias_sem_treinar,
        "dias_em_atraso": dias_em_atraso,
        "detrator_recente": detrator,
        "total_de_checkins": total_de_checkins,
    }


def atualizar_perfis_de_risco(rede, dry_run: bool = False) -> dict:
    """Recalcula o risco dos alunos ativos. Com ``dry_run`` mostra o que mudaria, sem gravar."""
    from usuarios.models import Usuario

    alunos = Usuario.todos.filter(rede=rede, status_user="Ativo").select_related("unidade")
    criados = atualizados = 0
    mudancas = []
    for aluno in alunos:
        conta = calcular_risco(aluno)
        perfil = PerfilDeRisco.objects.filter(aluno=aluno).first()
        anterior = perfil.pontuacao if perfil else None
        if perfil is None:
            criados += 1
        else:
            atualizados += 1
        if anterior != conta["pontuacao"]:
            mudancas.append(
                {
                    "aluno": aluno.nome,
                    "de": anterior,
                    "para": conta["pontuacao"],
                    "faixa": conta["faixa"],
                }
            )
        if dry_run:
            continue
        if perfil is None:
            perfil = PerfilDeRisco(rede=rede, aluno=aluno)
        perfil.unidade = aluno.unidade
        perfil.pontuacao = conta["pontuacao"]
        perfil.faixa = conta["faixa"]
        perfil.motivos = conta["motivos"]
        perfil.dias_sem_treinar = conta["dias_sem_treinar"]
        perfil.dias_em_atraso = conta["dias_em_atraso"]
        perfil.detrator_recente = conta["detrator_recente"]
        perfil.total_de_checkins = conta["total_de_checkins"]
        perfil.acao = conta["acao"]
        perfil.save()
    return {
        "alunos": alunos.count(),
        "criados": criados,
        "atualizados": atualizados,
        "mudancas": mudancas[:50],
        "dry_run": dry_run,
    }


def registrar_desfecho(
    *, perfil: PerfilDeRisco, desfecho: str, observacoes: str = "", responsavel=None
) -> PerfilDeRisco:
    if desfecho not in dict(PerfilDeRisco.Desfecho.choices):
        raise ErroDeRelacionamento("Desfecho desconhecido.")
    perfil.desfecho = desfecho
    perfil.observacoes = observacoes
    if responsavel is not None:
        perfil.responsavel = responsavel
    perfil.acao_definida_em = timezone.now()
    perfil.save(update_fields=["desfecho", "observacoes", "responsavel", "acao_definida_em"])
    return perfil


def resumo_da_retencao(rede) -> dict:
    perfis = PerfilDeRisco.objects.filter(rede=rede)
    por_faixa = {
        valor: perfis.filter(faixa=valor).count() for valor, _r in PerfilDeRisco.Faixa.choices
    }
    return {
        "total": perfis.count(),
        "por_faixa": por_faixa,
        "pedem_acao": perfis.filter(
            faixa__in=[PerfilDeRisco.Faixa.ALTO, PerfilDeRisco.Faixa.CRITICO]
        ).count(),
        "em_aberto": perfis.filter(desfecho=PerfilDeRisco.Desfecho.EM_ABERTO).count(),
        "recuperados": perfis.filter(desfecho=PerfilDeRisco.Desfecho.RECUPERADO).count(),
        "sem_perfil": _alunos_sem_perfil(rede),
    }


def _alunos_sem_perfil(rede) -> int:
    from usuarios.models import Usuario

    return (
        Usuario.todos.filter(rede=rede, status_user="Ativo")
        .annotate(quantos=Count("perfis_de_risco"))
        .filter(quantos=0)
        .count()
    )


def matricular_lead(*, lead: Lead, criado_por=None, plano=None, unidade=None):
    """Cria o aluno a partir do lead e fecha a conversao.

    O login nasce com senha inutilizavel (o aluno define a dele no primeiro acesso), porque criar
    senha provisoria em nome de outra pessoa e como nascem contas orfas.
    """
    from django.contrib.auth import get_user_model

    from usuarios.models import Usuario

    modelo_de_login = get_user_model()
    base = (lead.email.split("@")[0] if lead.email else "").strip().lower()
    if not base:
        base = "".join(caractere for caractere in (lead.telefone or "") if caractere.isdigit())
    base = base or f"lead{lead.pk}"
    login_disponivel = base
    contador = 1
    while modelo_de_login.objects.filter(username=login_disponivel).exists():
        contador += 1
        login_disponivel = f"{base}{contador}"
    conta = modelo_de_login.objects.create_user(
        username=login_disponivel,
        email=lead.email or "",
        password=None,
    )
    conta.set_unusable_password()
    conta.save(update_fields=["password"])
    perfil = Usuario.todos.create(
        rede=lead.rede,
        unidade=unidade or lead.unidade,
        user=conta,
        nome=lead.nome,
        status_user="Ativo",
    )
    converter_lead(lead=lead, aluno=perfil, plano=plano)
    if criado_por is not None and lead.responsavel is None:
        lead.responsavel = criado_por
        lead.save(update_fields=["responsavel"])
    return lead, perfil
