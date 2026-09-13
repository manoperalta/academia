"""Servicos do painel do professor: agenda, turma, presenca, alunos e comissoes.

O professor enxerga **apenas o que e dele** — as turmas em que e responsavel, os alunos dessas turmas
e os treinos que prescreveu. E o mesmo principio do escopo por rede, um nivel abaixo.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from agendamento.models import Agendamento
from painel.models import Painel, PainelItem
from painel_do_professor.models import (
    AulaDaDisponibilidade,
    DisponibilidadeDoProfessor,
    OcorrenciaDaTurma,
    SubstituicaoDeTurma,
    TurmaMaterializada,
)
from professores.models import Professor
from treinos.models import AvaliacaoFisica, Treino
from usuarios.models import Usuario

#: Quantas semanas de agenda a materializacao cobre a frente (decisao do dono do produto).
SEMANAS_PADRAO = 8

SITUACOES_DE_PRESENCA = {"presente": "Concluido", "falta": "Faltou", "cancelado": "Cancelado"}


class ErroDoProfessor(Exception):
    """Falha esperada no painel do professor."""


def professor_do_usuario(usuario, rede=None) -> Professor | None:
    """Liga o login ao perfil de professor (o vinculo e pelo OneToOne ``user``)."""
    consulta = Professor.todos.filter(user=usuario)
    if rede is not None:
        consulta = consulta.filter(rede=rede)
    return consulta.first()


def turmas_do_professor(professor, de: date | None = None, ate: date | None = None):
    """Turmas em que ele e responsavel (ou substituto registrado)."""
    consulta = Painel.todos.filter(
        responsavel=professor.user, arquivado_em__isnull=True
    ).select_related("unidade")
    if de is not None:
        consulta = consulta.filter(data__gte=de)
    if ate is not None:
        consulta = consulta.filter(data__lte=ate)
    return consulta.order_by("data", "hora_inicio")


def agenda_do_dia(professor, dia: date | None = None) -> dict:
    dia = dia or timezone.localdate()
    turmas = list(turmas_do_professor(professor, de=dia, ate=dia))
    agendamentos = Agendamento.todos.filter(
        painel__in=turmas, arquivado_em__isnull=True
    ).select_related("aluno", "painel")
    por_turma = {}
    for agendamento in agendamentos:
        por_turma.setdefault(agendamento.painel_id, []).append(agendamento)
    return {
        "dia": dia,
        "turmas": [
            {
                "turma": turma,
                "aulas": [item.aula for item in turma.itens.select_related("aula")],
                "agendamentos": por_turma.get(turma.pk, []),
                "ocupacao": len(por_turma.get(turma.pk, [])),
                "capacidade": turma.numero_de_user,
            }
            for turma in turmas
        ],
        "total_de_alunos": agendamentos.count(),
        "presencas": agendamentos.filter(status="Concluido").count(),
        "faltas": agendamentos.filter(status="Faltou").count(),
    }


def semana_do_professor(professor, inicio: date | None = None) -> list[dict]:
    inicio = inicio or (timezone.localdate() - timedelta(days=timezone.localdate().weekday()))
    dias = []
    for deslocamento in range(7):
        dia = inicio + timedelta(days=deslocamento)
        agenda = agenda_do_dia(professor, dia)
        dias.append({"dia": dia, "turmas": agenda["turmas"], "alunos": agenda["total_de_alunos"]})
    return dias


def marcar_presenca(
    *, agendamento: Agendamento, situacao: str, professor: Professor
) -> Agendamento:
    """O professor fecha a chamada; so mexe em agendamento das proprias turmas."""
    if situacao not in SITUACOES_DE_PRESENCA:
        raise ErroDoProfessor("Situacao de presenca desconhecida.")
    if agendamento.painel.responsavel_id != professor.user_id:
        raise ErroDoProfessor("Esta turma nao e sua.")
    agendamento.status = situacao
    agendamento.save(update_fields=["status"])
    return agendamento


def chamada_do_dia(*, turma: Painel, professor: Professor, presencas: dict) -> dict:
    """Fecha a chamada de uma turma de uma vez (id por id)."""
    if turma.responsavel_id != professor.user_id:
        raise ErroDoProfessor("Esta turma nao e sua.")
    atualizados = 0
    for agendamento in Agendamento.todos.filter(painel=turma, arquivado_em__isnull=True):
        situacao = presencas.get(str(agendamento.pk))
        if situacao in SITUACOES_DE_PRESENCA:
            agendamento.status = situacao
            agendamento.save(update_fields=["status"])
            atualizados += 1
    return {"turma": turma, "atualizados": atualizados}


def registrar_ocorrencia(
    *, turma: Painel, aluno: Usuario, professor: Professor, tipo: str, descricao: str
) -> OcorrenciaDaTurma:
    if not (descricao or "").strip():
        raise ErroDoProfessor("Descreva a ocorrencia.")
    if tipo not in dict(OcorrenciaDaTurma.Tipo.choices):
        raise ErroDoProfessor("Tipo de ocorrencia desconhecido.")
    return OcorrenciaDaTurma.objects.create(
        turma=turma, aluno=aluno, professor=professor, tipo=tipo, descricao=descricao.strip()
    )


@transaction.atomic
def registrar_substituicao(
    *, turma: Painel, substituto: Professor, motivo: str = ""
) -> SubstituicaoDeTurma:
    """Transfere a turma para outro professor, deixando o rastro de quem assumiu por que."""
    titular = professor_do_usuario(turma.responsavel, rede=turma.rede)
    if titular is None:
        raise ErroDoProfessor("A turma nao tem professor responsavel cadastrado.")
    if substituto.pk == titular.pk:
        raise ErroDoProfessor("O substituto tem de ser outro professor.")
    substituicao = SubstituicaoDeTurma.objects.create(
        turma=turma, titular=titular, substituto=substituto, motivo=motivo[:200]
    )
    turma.responsavel = substituto.user
    turma.save(update_fields=["responsavel"])
    return substituicao


def ocorrencias_da_turma(turma: Painel, limite: int = 50):
    return turma.ocorrencias.select_related("aluno").order_by("-criado_em")[:limite]


# ------------------------------------------------------------------ alunos
def meus_alunos(professor, limite: int = 200):
    """Alunos que aparecem nas minhas turmas ou nos treinos que prescrevi."""
    das_turmas = Agendamento.todos.filter(
        painel__responsavel=professor.user, arquivado_em__isnull=True
    ).values_list("aluno_id", flat=True)
    dos_treinos = Treino.objects.filter(professor=professor).values_list(
        "aluno__user_id", flat=True
    )
    identificadores = set(das_turmas) | set(dos_treinos)
    return Usuario.todos.filter(rede=professor.rede, user_id__in=identificadores)[:limite]


def frequencia_do_aluno(aluno, dias: int = 90) -> dict:
    desde = timezone.now() - timedelta(days=dias)
    agendamentos = Agendamento.todos.filter(
        aluno=aluno.user, data_agendamento__gte=desde, arquivado_em__isnull=True
    )
    total = agendamentos.count()
    presencas = agendamentos.filter(status="Concluido").count()
    return {
        "dias": dias,
        "agendamentos": total,
        "presencas": presencas,
        "faltas": agendamentos.filter(status="Faltou").count(),
        "taxa_de_presenca": round(presencas * 100 / total, 1) if total else 0.0,
    }


def avaliacoes_do_aluno(aluno, limite: int = 24):
    return AvaliacaoFisica.objects.filter(aluno=aluno)[:limite]


# ------------------------------------------------------------------ comissoes
def meu_financeiro(professor, referencia=None) -> dict:
    """O que o professor precisa ver: valor da hora, horas do mes e a previsao do repasse.

    O valor da hora vem do painel do admin/gestor (regra ``por_hora`` vigente) -- o professor
    confere o numero, nao define.
    """
    from remuneracao.servicos import ErroDeRemuneracao, calcular_apuracao, competencia
    from remuneracao.servicos import horas_trabalhadas

    inicio, fim = competencia(referencia)
    horas, fonte = horas_trabalhadas(professor, professor.unidade, inicio, fim)
    previsao = None
    pendencia = ""
    try:
        calculo = calcular_apuracao(professor, professor.unidade, inicio, fim)
        previsao = calculo["total"]
        linhas = calculo["linhas"]
    except ErroDeRemuneracao as erro:
        pendencia = str(erro)
        linhas = []
    return {
        "valor_por_hora": professor.valor_por_hora,
        "horas_no_mes": horas,
        "fonte_das_horas": fonte,
        "inicio": inicio,
        "fim": fim,
        "previsao": previsao,
        "linhas": linhas,
        "pendencia": pendencia,
    }


def minhas_comissoes(professor, limite: int = 24) -> dict:
    """Extrato do proprio trabalho: apuracoes por competencia e quanto ja foi pago."""
    from remuneracao.models import ApuracaoDeComissao

    apuracoes = (
        ApuracaoDeComissao.objects.filter(professor=professor)
        .select_related("unidade")
        .order_by("-inicio")[:limite]
    )
    total = Decimal("0")
    pago = Decimal("0")
    for apuracao in apuracoes:
        total += apuracao.valor_devido or Decimal("0")
        if getattr(apuracao, "pago_em", None):
            pago += apuracao.valor_devido or Decimal("0")
    return {
        "apuracoes": list(apuracoes),
        "total_devido": total,
        "total_pago": pago,
        "a_receber": total - pago,
    }


# =============================================================== AGENDA DO PROFESSOR
def disponibilidades_do_professor(professor, incluir_encerradas: bool = False):
    """Blocos de agenda do professor (por dia da semana, na ordem de exibicao)."""
    consulta = DisponibilidadeDoProfessor.todos.filter(professor=professor)
    if not incluir_encerradas:
        consulta = consulta.filter(ativo=True)
    return consulta.order_by("dia_da_semana", "hora_inicio")


def datas_do_bloco(
    disponibilidade, *, hoje: date | None = None, semanas: int = SEMANAS_PADRAO
) -> list[date]:
    """Datas em que o bloco cai dentro da janela de materializacao."""
    hoje = hoje or timezone.localdate()
    if semanas < 1:
        return []
    fim = hoje + timedelta(days=semanas * 7 - 1)
    datas = []
    for deslocamento in range((fim - hoje).days + 1):
        dia = hoje + timedelta(days=deslocamento)
        if dia.weekday() != disponibilidade.dia_da_semana:
            continue
        if disponibilidade.alcanca(dia):
            datas.append(dia)
    return datas


def compor_compromisso(disponibilidade, aulas) -> list[AulaDaDisponibilidade]:
    """Define (substituindo) as aulas que compoem o compromisso, na ordem informada."""
    if not aulas:
        raise ErroDoProfessor("Escolha pelo menos uma aula para compor o compromisso.")
    disponibilidade.composicao.all().delete()
    return [
        AulaDaDisponibilidade.objects.create(
            disponibilidade=disponibilidade, aula=aula, ordem=ordem
        )
        for ordem, aula in enumerate(aulas, start=1)
    ]


def aviso_de_composicao(disponibilidade) -> str:
    """Aviso (nunca bloqueio) quando os videos somam menos que o tempo do compromisso.

    Os videos so tem duracao quando o arquivo foi processado; sem esse dado, a conta nao e
    inventada -- e a tela simplesmente nao avisa.
    """
    minutos = disponibilidade.minutos_de_video()
    if not minutos or not disponibilidade.duracao_minutos:
        return ""
    if minutos < disponibilidade.duracao_minutos:
        return (
            f"Os videos deste compromisso somam {minutos} min e o compromisso dura "
            f"{disponibilidade.duracao_minutos} min. Confira se a composicao fecha o tempo."
        )
    return ""


def tipos_de_atividade(turma) -> dict:
    """Tipo do compromisso para o aluno: categorias das aulas, restricoes e a lista de videos."""
    aulas = [item.aula for item in turma.itens.select_related("aula").order_by("ordem")]
    categorias = []
    for aula in aulas:
        rotulo = aula.get_categorias_exercicios_display()
        if rotulo not in categorias:
            categorias.append(rotulo)
    restricoes = []
    for aula in aulas:
        if aula.restricao and aula.restricao != "nenhuma":
            rotulo = aula.get_restricao_display()
            if rotulo not in restricoes:
                restricoes.append(rotulo)
    return {
        "aulas": aulas,
        "categorias": categorias,
        "restricoes": restricoes,
        "total_de_aulas": len(aulas),
    }


def _sincronizar_aulas_da_turma(turma, aulas) -> int:
    """Deixa os itens da turma iguais as aulas do bloco, preservando o que ja existe."""
    existentes = {item.aula_id: item for item in turma.itens.all()}
    alterados = 0
    for ordem, aula in enumerate(aulas, start=1):
        item = existentes.pop(aula.pk, None)
        if item is None:
            PainelItem.todos.create(
                painel=turma, aula=aula, ordem=ordem, rede=turma.rede, unidade=turma.unidade
            )
            alterados += 1
        elif item.ordem != ordem:
            item.ordem = ordem
            item.save(update_fields=["ordem"])
            alterados += 1
    for sobrando in existentes.values():
        sobrando.delete()
        alterados += 1
    return alterados


def _turmas_com_agendamento(turma) -> bool:
    return Agendamento.todos.filter(painel=turma, arquivado_em__isnull=True).exists()


def materializar_disponibilidade(
    disponibilidade,
    *,
    semanas: int = SEMANAS_PADRAO,
    hoje: date | None = None,
    dry_run: bool = False,
) -> dict:
    """Cria/atualiza as turmas que o bloco gera na janela de semanas.

    Idempotente pela chave natural (rede, responsavel, data, hora de inicio) e seguro com dado
    vivo: turma que ja tem aluno agendado **nunca** e apagada -- ela fica e o motivo entra em
    ``avisos``. ``dry_run`` conta o que faria, sem gravar.
    """
    from django.db import transaction

    resultado = {"criadas": 0, "atualizadas": 0, "arquivadas": 0, "preservadas": 0, "avisos": []}
    hoje = hoje or timezone.localdate()
    if disponibilidade.professor is None or disponibilidade.professor.user_id is None:
        raise ErroDoProfessor("O professor deste bloco nao tem acesso de login vinculado.")

    aulas = disponibilidade.aulas_compostas()
    aviso = aviso_de_composicao(disponibilidade)
    if aviso:
        resultado["avisos"].append(aviso)

    desejadas = {
        (data, inicio): fim
        for data in datas_do_bloco(disponibilidade, hoje=hoje, semanas=semanas)
        for inicio, fim in disponibilidade.horarios()
    }

    rastros = {
        (rastro.turma.data, rastro.turma.hora_inicio): rastro
        for rastro in TurmaMaterializada.objects.filter(disponibilidade=disponibilidade).select_related(
            "turma"
        )
    }

    with transaction.atomic():
        for (data, inicio), fim in sorted(desejadas.items()):
            rastro = rastros.get((data, inicio))
            turma = rastro.turma if rastro else None
            if turma is None:
                turma = Painel.todos.filter(
                    rede=disponibilidade.rede,
                    responsavel=disponibilidade.professor.user,
                    data=data,
                    hora_inicio=inicio,
                    arquivado_em__isnull=True,
                ).first()
            if turma is None:
                resultado["criadas"] += 1
                if dry_run:
                    continue
                turma = Painel.todos.create(
                    rede=disponibilidade.rede,
                    unidade=disponibilidade.unidade,
                    nome=disponibilidade.nome,
                    data=data,
                    hora_inicio=inicio,
                    hora_fim=fim,
                    responsavel=disponibilidade.professor.user,
                    numero_de_user=disponibilidade.vagas_por_horario,
                )
                TurmaMaterializada.objects.create(disponibilidade=disponibilidade, turma=turma)
            else:
                if rastro is None:
                    TurmaMaterializada.objects.create(disponibilidade=disponibilidade, turma=turma)
                conflito = rastro and rastro.disponibilidade_id != disponibilidade.pk
                if conflito:
                    resultado["preservadas"] += 1
                    resultado["avisos"].append(
                        f"{turma.data:%d/%m} {inicio:%H:%M}: ja e de outro bloco de agenda; nao mexi."
                    )
                    continue
                if _turmas_com_agendamento(turma):
                    resultado["preservadas"] += 1
                    resultado["avisos"].append(
                        f"{turma.data:%d/%m} {inicio:%H:%M}: tem aluno agendado; "
                        f"so as aulas foram sincronizadas."
                    )
                else:
                    turma.hora_fim = fim
                    turma.nome = disponibilidade.nome
                    turma.numero_de_user = disponibilidade.vagas_por_horario
                    turma.unidade = turma.unidade or disponibilidade.unidade
                    turma.arquivado_em = None
                    turma.save(
                        update_fields=[
                            "hora_fim",
                            "nome",
                            "numero_de_user",
                            "unidade",
                            "arquivado_em",
                        ]
                    )
                    resultado["atualizadas"] += 1
            if not dry_run and aulas:
                _sincronizar_aulas_da_turma(turma, aulas)

        # o que a recorrencia nao gera mais: arquiva o que ninguem agendou
        for chave, rastro in rastros.items():
            if chave in desejadas:
                continue
            turma = rastro.turma
            if _turmas_com_agendamento(turma):
                resultado["preservadas"] += 1
                resultado["avisos"].append(
                    f"{turma.data:%d/%m} {turma.hora_inicio:%H:%M}: fora da nova agenda, "
                    f"mas tem aluno agendado; mantida."
                )
                continue
            resultado["arquivadas"] += 1
            if dry_run:
                continue
            turma.arquivar()
            rastro.delete()
    return resultado


def materializar_agenda(
    professor, *, semanas: int = SEMANAS_PADRAO, dry_run: bool = False
) -> dict:
    """Materializa todos os blocos abertos do professor e resume o que mudou."""
    total = {"criadas": 0, "atualizadas": 0, "arquivadas": 0, "preservadas": 0, "avisos": []}
    for disponibilidade in disponibilidades_do_professor(professor):
        parcial = materializar_disponibilidade(disponibilidade, semanas=semanas, dry_run=dry_run)
        for chave in ("criadas", "atualizadas", "arquivadas", "preservadas"):
            total[chave] += parcial[chave]
        total["avisos"].extend(parcial["avisos"])
    return total


def encerrar_disponibilidade(disponibilidade, *, arquivar_futuras: bool = True) -> dict:
    """Fecha o bloco e tira do ar as turmas futuras que ele gerou e ninguem agendou."""
    disponibilidade.ativo = False
    disponibilidade.save(update_fields=["ativo", "atualizado_em"])
    resultado = {"arquivadas": 0, "preservadas": 0}
    if not arquivar_futuras:
        return resultado
    hoje = timezone.localdate()
    for rastro in TurmaMaterializada.objects.filter(
        disponibilidade=disponibilidade
    ).select_related("turma"):
        turma = rastro.turma
        if turma.data < hoje or _turmas_com_agendamento(turma):
            resultado["preservadas"] += 1
            continue
        turma.arquivar()
        rastro.delete()
        resultado["arquivadas"] += 1
    return resultado


def agenda_aberta_do_professor(professor, *, semanas: int = SEMANAS_PADRAO, hoje: date | None = None):
    """Horarios futuros que o professor tem abertos (o que o aluno pode reservar)."""
    hoje = hoje or timezone.localdate()
    return (
        Painel.todos.filter(
            responsavel=professor.user,
            data__gte=hoje,
            data__lte=hoje + timedelta(days=semanas * 7 - 1),
            arquivado_em__isnull=True,
        )
        .select_related("unidade")
        .order_by("data", "hora_inicio")
    )
