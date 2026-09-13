"""Servicos do controle de acesso e da conciliacao com parceiros.

``decidir_acesso`` e o coracao: resolve a credencial, confere se o aluno pode entrar (mensalidade
em dia ou autorizacao do parceiro dentro do limite), registra a tentativa e, quando libera, tambem
gera o check-in — para o aluno nao ter de "bater o ponto" duas vezes.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from acesso.models import (
    CredencialDeAcesso,
    DispositivoDeAcesso,
    ExtratoDeParceiro,
    LinhaDeExtrato,
    PlanoDeParceiro,
    RegistroDeAcesso,
)

#: Janela em que leituras seguidas da mesma credencial nao contam como nova entrada.
SEGUNDOS_DE_ANTI_PASSBACK = 60
MAPA_DE_ORIGEM_DO_CHECKIN = {
    RegistroDeAcesso.Origem.CATRACA: "catraca",
    RegistroDeAcesso.Origem.TOTEM: "totem",
    RegistroDeAcesso.Origem.APLICATIVO: "pwa",
    RegistroDeAcesso.Origem.MANUAL: "manual",
    RegistroDeAcesso.Origem.PORTARIA: "manual",
}


class ErroDeAcesso(Exception):
    """Falha esperada no fluxo de acesso ou de conciliacao."""


# ------------------------------------------------------------------ credenciais
def emitir_credencial(
    *, aluno, codigo: str, tipo: str = CredencialDeAcesso.Tipo.CARTAO, ativa: bool = True
) -> CredencialDeAcesso:
    codigo = (codigo or "").strip()
    if not codigo:
        raise ErroDeAcesso("Informe o codigo da credencial.")
    if tipo not in dict(CredencialDeAcesso.Tipo.choices):
        raise ErroDeAcesso("Tipo de credencial desconhecido.")
    credencial, _criada = CredencialDeAcesso.objects.update_or_create(
        rede=aluno.rede,
        codigo=codigo,
        defaults={"aluno": aluno, "tipo": tipo, "ativa": ativa},
    )
    return credencial


def cancelar_credencial(credencial: CredencialDeAcesso, motivo: str = "") -> CredencialDeAcesso:
    credencial.ativa = False
    credencial.perdida_em = timezone.now()
    credencial.save(update_fields=["ativa", "perdida_em"])
    return credencial


# ------------------------------------------------------------------ decisao de acesso
def _vigencia_em_dia(aluno, hoje: date) -> bool:
    from financeiro.models import Pagamento

    # Manager global de proposito: a catraca decide fora do contexto de tenant do painel.
    return Pagamento.todos.filter(
        rede=aluno.rede, usuario=aluno.user, status="pago", data_fim__gte=hoje
    ).exists()


def _autorizacao_do_parceiro(aluno, codigo: str, hoje: date):
    """(autorizado, plano, motivo) — o parceiro manda a lista de quem pode treinar."""
    competencia = hoje.replace(day=1)
    linhas = LinhaDeExtrato.objects.filter(
        extrato__rede=aluno.rede, extrato__competencia=competencia, codigo=codigo
    ).select_related("extrato", "extrato__plano_de_parceiro")
    linha = linhas.filter(data=hoje).first() or linhas.first()
    if linha is None:
        return False, None, ""
    plano = linha.extrato.plano_de_parceiro
    if not plano.ativo:
        return False, plano, "plano de parceiro inativo"
    if plano.limite_de_acessos_por_mes:
        usados = RegistroDeAcesso.objects.filter(
            rede=aluno.rede,
            credencial__codigo=codigo,
            liberado=True,
            criado_em__date__gte=competencia,
            criado_em__date__lte=hoje,
        ).count()
        if usados >= plano.limite_de_acessos_por_mes:
            return (
                False,
                plano,
                f"limite de {plano.limite_de_acessos_por_mes} acesso(s) do parceiro atingido",
            )
    return True, plano, f"autorizado por {plano.get_parceiro_display()}"


def decidir_acesso(
    *,
    rede,
    unidade,
    codigo: str = "",
    aluno=None,
    origem: str = "catraca",
    dispositivo: DispositivoDeAcesso | None = None,
    agora=None,
) -> dict:
    """Decide, registra e (quando libera) gera o check-in. Nunca levanta excecao por negativa."""
    momento = agora or timezone.now()
    hoje = momento.date()
    if origem not in dict(RegistroDeAcesso.Origem.choices):
        raise ErroDeAcesso("Origem de acesso desconhecida.")
    if dispositivo is not None:
        dispositivo.ultima_comunicacao_em = momento
        dispositivo.save(update_fields=["ultima_comunicacao_em"])

    credencial = None
    codigo = (codigo or "").strip()
    if aluno is None and codigo:
        credencial = (
            CredencialDeAcesso.objects.filter(rede=rede, codigo=codigo)
            .select_related("aluno", "aluno__unidade")
            .first()
        )
        if credencial is not None:
            aluno = credencial.aluno

    liberado, motivo = False, ""
    if aluno is None:
        motivo = "credencial nao reconhecida nesta rede"
    else:
        if credencial is not None and not credencial.ativa:
            motivo = "credencial cancelada"
        elif dispositivo is not None and not dispositivo.ativo:
            motivo = "dispositivo inativo"
        elif (getattr(aluno, "status_user", "") or "").lower() != "ativo":
            motivo = f"aluno com situacao '{aluno.status_user}'"
        else:
            autorizado_pelo_parceiro, plano, explicacao = _autorizacao_do_parceiro(
                aluno, codigo, hoje
            )
            if _vigencia_em_dia(aluno, hoje) or autorizado_pelo_parceiro:
                liberado, motivo = True, ""
            elif plano is not None:
                motivo = explicacao or "acesso negado pelo parceiro"
            else:
                motivo = "mensalidade vencida ou sem vigencia"

    registro = RegistroDeAcesso.objects.create(
        rede=rede,
        unidade=unidade,
        aluno=aluno,
        credencial=credencial,
        dispositivo=dispositivo,
        liberado=liberado,
        motivo=motivo,
        origem=origem,
        codigo_apresentado=codigo,
        itinerante=bool(aluno and aluno.unidade_id and aluno.unidade_id != unidade.pk),
    )

    duplicado = False
    if liberado and aluno is not None:
        anterior = (
            RegistroDeAcesso.objects.filter(
                rede=rede, aluno=aluno, liberado=True, criado_em__lt=momento
            )
            .order_by("-criado_em")
            .first()
        )
        if (
            anterior is not None
            and (momento - anterior.criado_em).total_seconds() <= SEGUNDOS_DE_ANTI_PASSBACK
        ):
            duplicado = True
        else:
            _registrar_checkin(aluno, unidade, origem)
    return {
        "liberado": liberado,
        "motivo": motivo,
        "aluno": aluno,
        "registro": registro,
        "duplicado": duplicado,
        "checkin_gerado": liberado and not duplicado,
    }


def _registrar_checkin(aluno, unidade, origem: str) -> None:
    """Gera o check-in do app do aluno (que pontua na gamificacao)."""
    try:
        from area_do_aluno.servicos import ErroDeCheckin, registrar_checkin

        registrar_checkin(aluno, unidade, origem=MAPA_DE_ORIGEM_DO_CHECKIN.get(origem, "manual"))
    except ErroDeCheckin:
        # check-in duplicado ou fora da regra nao invalida a entrada fisica ja liberada
        return
    except Exception:  # pragma: no cover - integracao nao pode derrubar a catraca
        return


def liberar_manualmente(*, rede, unidade, aluno, motivo: str = "", liberado_por=None) -> dict:
    resultado = decidir_acesso(rede=rede, unidade=unidade, aluno=aluno, origem="manual")
    registro = resultado["registro"]
    if liberado_por is not None:
        registro.motivo = (registro.motivo or motivo or "")[:200]
        registro.save(update_fields=["motivo"])
    return resultado


def resumo_do_acesso(rede, dias: int = 30) -> dict:
    desde = timezone.now() - timedelta(days=dias)
    registros = RegistroDeAcesso.objects.filter(rede=rede, criado_em__gte=desde)
    negados = registros.filter(liberado=False)
    motivos: dict[str, int] = {}
    for registro in negados.order_by()[:500]:
        motivos[registro.motivo or "sem motivo"] = (
            motivos.get(registro.motivo or "sem motivo", 0) + 1
        )
    ordenados = sorted(motivos.items(), key=lambda item: -item[1])[:5]
    total = registros.count()
    liberados = registros.filter(liberado=True).count()
    return {
        "dias": dias,
        "total": total,
        "liberados": liberados,
        "negados": total - liberados,
        "taxa_de_liberacao": round(liberados * 100 / total, 1) if total else 0.0,
        "itinerantes": registros.filter(itinerante=True).count(),
        "motivos": ordenados,
    }


# ------------------------------------------------------------------ parceiros
ALIASES = {
    "data": {"data", "date", "dia"},
    "codigo": {"codigo", "code", "id", "matricula", "codigo do aluno", "identificador"},
    "nome": {"nome", "name", "aluno", "nome do aluno"},
    "valor": {"valor", "value", "preco", "amount", "valor do acesso"},
}


def _normalizar(chave: str) -> str:
    return (chave or "").strip().lower().replace('"', "")


def importar_extrato(
    *,
    plano_de_parceiro: PlanoDeParceiro,
    competencia: date,
    conteudo: str,
    nome_do_arquivo: str = "",
) -> ExtratoDeParceiro:
    """Le o CSV do parceiro (virgula ou ponto e virgula) e guarda as linhas para conciliar."""
    texto = (conteudo or "").strip()
    if not texto:
        raise ErroDeAcesso("Arquivo do extrato vazio.")
    if ExtratoDeParceiro.objects.filter(
        plano_de_parceiro=plano_de_parceiro, competencia=competencia
    ).exists():
        raise ErroDeAcesso("Ja existe extrato importado para esta competencia.")
    dialeto = csv.Sniffer().sniff(texto[:2000], delimiters=";,\t") if len(texto) > 20 else csv.excel
    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    if not leitor.fieldnames:
        raise ErroDeAcesso("Nao consegui ler o cabecalho do extrato.")

    colunas: dict[str, str] = {}
    for nome_original in leitor.fieldnames:
        normalizado = _normalizar(nome_original)
        for campo, apelidos in ALIASES.items():
            if normalizado in apelidos and campo not in colunas:
                colunas[campo] = nome_original
    faltando = [campo for campo in ("data", "codigo", "valor") if campo not in colunas]
    if faltando:
        raise ErroDeAcesso(f"O extrato precisa das colunas {', '.join(faltando)}.")

    extrato = ExtratoDeParceiro.objects.create(
        rede=plano_de_parceiro.rede,
        plano_de_parceiro=plano_de_parceiro,
        competencia=competencia,
        nome_do_arquivo=nome_do_arquivo,
    )
    total, valor_total = 0, Decimal("0")
    for linha in leitor:
        bruto = (linha.get(colunas["data"]) or "").strip()
        if not bruto:
            continue
        try:
            quando = _ler_data(bruto)
        except ValueError:
            continue
        try:
            valor = Decimal((linha.get(colunas["valor"]) or "0").replace(",", ".").strip())
        except InvalidOperation:
            valor = Decimal("0")
        LinhaDeExtrato.objects.create(
            extrato=extrato,
            data=quando,
            codigo=(linha.get(colunas["codigo"]) or "").strip(),
            nome_informado=(linha.get(colunas.get("nome", ""), "") or "").strip()
            if "nome" in colunas
            else "",
            valor=valor,
        )
        total += 1
        valor_total += valor
    extrato.total_de_acessos = total
    extrato.valor_total = valor_total
    extrato.save(update_fields=["total_de_acessos", "valor_total"])
    if total == 0:
        extrato.delete()
        raise ErroDeAcesso("Nenhuma linha valida encontrada no extrato.")
    return extrato


def _ler_data(bruto: str) -> date:
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return timezone.datetime.strptime(bruto, formato).date()
        except ValueError:
            continue
    raise ValueError(bruto)


def conciliar_extrato(extrato: ExtratoDeParceiro, dry_run: bool = False) -> dict:
    """Casa cada linha cobrada com um acesso liberado e aponta os dois lados do problema."""
    conciliadas, sem_acesso = 0, []
    for linha in extrato.linhas.all():
        registro = (
            RegistroDeAcesso.objects.filter(
                rede=extrato.rede,
                liberado=True,
                codigo_apresentado=linha.codigo,
                criado_em__date=linha.data,
            )
            .order_by("criado_em")
            .first()
        )
        if registro is None:
            sem_acesso.append({"data": linha.data, "codigo": linha.codigo, "valor": linha.valor})
            if not dry_run:
                linha.conciliado = False
                linha.divergencia = "cobranca sem acesso correspondente nesse dia"
                linha.save(update_fields=["conciliado", "divergencia"])
            continue
        conciliadas += 1
        if not dry_run:
            linha.conciliado = True
            linha.divergencia = ""
            linha.acesso = registro
            linha.save(update_fields=["conciliado", "divergencia", "acesso"])

    usados = set(extrato.linhas.values_list("acesso_id", flat=True))
    nao_faturados = [
        {
            "data": registro.criado_em.date(),
            "codigo": registro.codigo_apresentado,
            "aluno": str(registro.aluno or ""),
            "registro": registro.pk,
        }
        for registro in RegistroDeAcesso.objects.filter(
            rede=extrato.rede,
            liberado=True,
            criado_em__date__gte=extrato.competencia,
            criado_em__date__lte=_fim_da_competencia(extrato.competencia),
        ).exclude(pk__in=[pk for pk in usados if pk])
    ]

    resultado = {
        "extrato": extrato,
        "dry_run": dry_run,
        "linhas": extrato.linhas.count(),
        "conciliadas": conciliadas,
        "sem_acesso": sem_acesso,
        "nao_faturados": nao_faturados,
        "valor_no_extrato": extrato.valor_total,
        "valor_esperado": extrato.valor_esperado_pela_rede,
    }
    if not dry_run:
        extrato.situacao = (
            ExtratoDeParceiro.Situacao.CONCILIADO
            if not sem_acesso and not nao_faturados
            else ExtratoDeParceiro.Situacao.COM_DIVERGENCIA
        )
        extrato.conciliado_em = timezone.now()
        extrato.save(update_fields=["situacao", "conciliado_em"])
    return resultado


def _fim_da_competencia(competencia: date) -> date:
    proximo_mes = (competencia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return proximo_mes - timedelta(days=1)
