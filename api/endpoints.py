"""Endpoints da API v1 que nao sao CRUD de recurso (PRD 20.4/20.5)."""
from __future__ import annotations

from datetime import date

from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api import jwt as jwt_api
from api.tarefas import enfileirar


class EntrarComSenha(APIView):
    """POST /api/v1/auth/token/ -- usuario e senha devolvem JWT (acesso + renovacao)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identificador = (request.data.get("email") or request.data.get("username") or "").strip()
        senha = request.data.get("senha") or request.data.get("password") or ""
        usuario = authenticate(request, username=identificador, password=senha)
        if usuario is None:
            from django.contrib.auth import get_user_model

            perfil = get_user_model().objects.filter(email__iexact=identificador).first()
            if perfil is not None:
                usuario = authenticate(request, username=perfil.get_username(), password=senha)
        if usuario is None or not usuario.is_active:
            return Response({"title": "Credenciais invalidas", "status": 401,
                             "detail": "E-mail ou senha incorretos.", "codigo": "credenciais_invalidas"},
                            status=status.HTTP_401_UNAUTHORIZED)
        escopos = _escopos_do_usuario(usuario)
        extra = {"rede": getattr(request, "rede", None).pk if getattr(request, "rede", None) else None}
        return Response({
            "acesso": jwt_api.emitir(usuario.pk, escopos=escopos, tipo="acesso", extra=extra),
            "renovacao": jwt_api.emitir(usuario.pk, escopos=escopos, tipo="renovacao", extra=extra),
            "expira_em": jwt_api.VALIDADE_DO_ACESSO,
            "escopos": escopos,
        })


#: Escopos que cada papel do painel recebe na API (RF-API-004: menor escopo possivel).
ESCOPOS_POR_PAPEL = {
    "superadmin_plataforma": ["*"],
    "admin_rede": ["*"],
    "gestor_unidade": ["rede:read", "unidades:read", "alunos:read", "alunos:write",
                       "professores:read", "professores:write", "aulas:read", "aulas:write",
                       "agenda:read", "agenda:write", "financeiro:read", "comunicacao:read"],
    "recepcao": ["alunos:read", "alunos:write", "agenda:read", "agenda:write",
                 "financeiro:read", "unidades:read"],
    "professor": ["alunos:read", "aulas:read", "aulas:write", "agenda:read", "agenda:write"],
    "financeiro_rede": ["financeiro:read", "financeiro:write", "repasses:read", "repasses:write",
                        "alunos:read", "relatorios:read", "auditoria:read", "unidades:read"],
}


def _escopos_do_usuario(usuario) -> list[str]:
    vinculos = getattr(usuario, "vinculos", None)
    papeis = []
    if vinculos is not None:
        papeis = [vinculo.papel for vinculo in vinculos.filter(ativo=True)]
    if not papeis:
        return ["*"] if usuario.is_staff else []
    escopos: set[str] = set()
    for papel in papeis:
        escopos |= set(ESCOPOS_POR_PAPEL.get(papel, []))
    if usuario.is_staff:
        escopos |= {"plataforma:read", "plataforma:write", "auditoria:read"}
    return sorted(escopos)


class RenovarToken(APIView):
    """POST /api/v1/auth/refresh/ -- renova o acesso a partir do token de renovacao."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = request.data.get("renovacao") or ""
        try:
            dados = jwt_api.validar(token, tipo="renovacao")
        except jwt_api.TokenInvalido as erro:
            return Response({"title": "Token de renovacao invalido", "status": 401,
                             "detail": str(erro)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({"acesso": jwt_api.emitir(dados["sub"], escopos=dados.get("escopos"),
                                                 tipo="acesso"),
                         "expira_em": jwt_api.VALIDADE_DO_ACESSO})


class EstadoDoTenant(APIView):
    """GET /api/v1/estado/ -- o que o agente confere antes de operar (RF-API-014)."""

    def get(self, request):
        from api.models import TarefaAssincrona
        from governanca.models import RotinaAgendada

        rede = getattr(request, "rede", None)
        contexto = {
            "versao": "v1",
            "agora": timezone.now().isoformat(),
            "usuario": getattr(request.user, "get_username", lambda: None)() if request.user.is_authenticated else None,
            "escopos": sorted(getattr(request, "escopos_do_token", []) or []),
            "integracao": {"webhooks": _contar("webhooks"), "tarefas_na_fila": _contar("tarefas")},
            "rotinas": [
                {"nome": rotina.nome, "situacao": rotina.ultima_situacao or "nunca",
                 "ultima_execucao": rotina.ultima_execucao, "atrasada": rotina.atrasada}
                for rotina in RotinaAgendada.objects.filter(ativa=True)
            ],
            "tarefas": {"na_fila": TarefaAssincrona.objects.filter(
                situacao=TarefaAssincrona.Situacao.NA_FILA).count()},
        }
        if rede is not None:
            contexto["rede"] = {"id": rede.pk, "nome": rede.nome, "status": rede.status,
                                "dominio": rede.dominio or None,
                                "dominio_status": rede.dominio_status}
            contexto["limites"] = _limites_da_rede(rede)
        return Response(contexto)


def _limites_da_rede(rede) -> dict:
    """Uso atual contra os limites do pacote (o agente confere antes de criar)."""
    from core.models import Unidade
    from plataforma.servicos import assinatura_da
    from professores.models import Professor
    from usuarios.models import Usuario

    assinatura = assinatura_da(rede)
    pacote = getattr(assinatura, "pacote", None)
    uso = {
        "alunos": Usuario.todos.filter(rede=rede, status_user="Ativo").count(),
        "professores": Professor.todos.filter(rede=rede).count(),
        "unidades": Unidade.objects.filter(rede=rede).exclude(status="inativa").count(),
    }
    limites = {
        "pacote": getattr(pacote, "nome", None),
        "alunos": getattr(pacote, "limite_alunos", None),
        "professores": getattr(pacote, "limite_professores", None),
        "unidades": getattr(pacote, "limite_unidades", None),
    }
    return {"uso": uso, "limites": limites,
            "restantes": {chave: (None if limites.get(chave) is None
                                  else max(0, limites[chave] - valor))
                          for chave, valor in uso.items()}}


def _contar(chave: str) -> int:
    from api.models import EntregaDeWebhook, TarefaAssincrona, WebhookDeSaida

    if chave == "webhooks":
        return WebhookDeSaida.objects.filter(estado="ativo").count()
    if chave == "tarefas":
        return TarefaAssincrona.objects.filter(situacao=TarefaAssincrona.Situacao.NA_FILA).count()
    return EntregaDeWebhook.objects.filter(situacao="falhou").count()


class MetricasDaRede(APIView):
    """GET /api/v1/metricas-da-rede/ -- consolidado da rede para o agente (RF-API-009)."""

    def get(self, request):
        from rede.servicos import comparativo_entre_unidades, consolidado_da_rede

        rede = getattr(request, "rede", None)
        if rede is None:
            return Response({"title": "Contexto de rede ausente", "status": 400,
                             "detail": "Use o token de uma rede ou o dominio do cliente."},
                            status=status.HTTP_400_BAD_REQUEST)
        inicio = _data(request.query_params.get("inicio")) or timezone.localdate().replace(day=1)
        fim = _data(request.query_params.get("fim")) or timezone.localdate()
        consolidado = consolidado_da_rede(rede, inicio, fim)
        return Response({
            "rede": rede.nome, "inicio": inicio, "fim": fim,
            "recebido": str(consolidado["recebido"]), "em_aberto": str(consolidado["em_aberto"]),
            "resultado": str(consolidado["resultado"]), "repasses": str(consolidado["repasses"]),
            "alunos_ativos": consolidado["alunos_ativos"],
            "unidades": [{"nome": linha["unidade"].nome, "recebido": str(linha["recebido"]),
                          "alunos": linha["alunos_ativos"], "posicao": linha["posicao"]}
                         for linha in comparativo_entre_unidades(rede, inicio, fim)],
        })


def _data(valor):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


class RelatorioDaApi(APIView):
    """POST /api/v1/relatorios/<tipo>/ -- gera o relatorio como job (RF-API-012)."""

    def post(self, request, tipo: str):
        from api.tarefas import TarefaDesconhecida

        rede = getattr(request, "rede", None)
        parametros = dict(request.data or {})
        parametros.update({"rede_id": getattr(rede, "pk", None),
                           "inicio": str(_data(parametros.get("inicio")) or timezone.localdate().replace(day=1)),
                           "fim": str(_data(parametros.get("fim")) or timezone.localdate()),
                           "recurso": tipo})
        try:
            tarefa = enfileirar("relatorio", rede=rede, parametros=parametros,
                                usuario=request.user if request.user.is_authenticated else None,
                                token=getattr(request, "auth", None))
        except TarefaDesconhecida as erro:
            return Response({"title": "Tipo desconhecido", "status": 400, "detail": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"tarefa": tarefa.pk, "situacao": tarefa.situacao,
                         "acompanhe": f"/api/v1/tarefas/{tarefa.pk}/",
                         "download": f"/api/v1/tarefas/{tarefa.pk}/download/"},
                        status=status.HTTP_202_ACCEPTED)


class JobDaApi(APIView):
    """GET /api/v1/jobs/<id>/ -- acompanhamento do job (RF-API-015)."""

    def get(self, request, pk: int):
        from api.models import TarefaAssincrona

        tarefa = TarefaAssincrona.objects.filter(pk=pk).first()
        if tarefa is None:
            return Response({"title": "Job inexistente", "status": 404}, status=status.HTTP_404_NOT_FOUND)
        return Response({"id": tarefa.pk, "tipo": tarefa.tipo, "situacao": tarefa.situacao,
                         "progresso": tarefa.progresso, "resultado": tarefa.resultado,
                         "erro": tarefa.erro, "expira_em": tarefa.termina_em,
                         "download": f"/api/v1/tarefas/{tarefa.pk}/download/"
                         if tarefa.arquivo else None})


class LgpdDaApi(APIView):
    """POST /api/v1/lgpd/titulares/<id>/<acao>/ -- exportar ou anonimizar (RF-TEN-021)."""

    def post(self, request, pk: int, acao: str):
        from api.tarefas import enfileirar

        if acao not in {"exportar", "anonimizar"}:
            return Response({"title": "Acao desconhecida", "status": 400}, status=status.HTTP_400_BAD_REQUEST)
        from usuarios.models import Usuario

        aluno = Usuario.todos.filter(pk=pk).first()
        if aluno is None:
            return Response({"title": "Titular nao encontrado", "status": 404}, status=status.HTTP_404_NOT_FOUND)
        tarefa = enfileirar("lgpd", rede=getattr(request, "rede", None),
                            parametros={"rede_id": getattr(getattr(request, "rede", None), "pk", None),
                                        "aluno_id": aluno.pk, "acao": acao},
                            usuario=request.user if request.user.is_authenticated else None)
        return Response({"tarefa": tarefa.pk, "acao": acao, "situacao": tarefa.situacao},
                        status=status.HTTP_202_ACCEPTED)


class InadimplenciaDaApi(APIView):
    """GET /api/v1/inadimplencia/ -- quem esta com pagamento aberto (RF-API-009)."""

    def get(self, request):
        from financeiro.models import Pagamento

        rede = getattr(request, "rede", None)
        consulta = Pagamento.objects.filter(status__in=["pendente", "em_analise"])
        if rede is not None:
            consulta = consulta.filter(rede=rede)
        return Response({"total": consulta.count(), "itens": [
            {"pagamento": item.pk, "aluno": item.usuario_id, "unidade": item.unidade_id,
             "valor": str(item.valor_pago), "vencimento": item.data_fim}
            for item in consulta.select_related("usuario")[:200]
        ]})


def playground(request):
    """Pagina de teste de integracao: envia uma chamada com o token escolhido (RF-API-016)."""
    from api.escopos import ESCOPOS
    from api.models import ApiToken

    return render(request, "api/playground.html", {
        "escopos": sorted(ESCOPOS.items()),
        "tokens": ApiToken.objects.filter(ativo=True).values_list("nome", "escopos")[:20],
        "recursos": [f"/api/v1/{slug}/" for slug in (
            "alunos", "unidades", "repasses", "pagamentos", "comunicados", "webhooks", "tarefas")],
    })
