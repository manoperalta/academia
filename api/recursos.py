"""Catalogo dos 30 recursos da API v1 (PRD 20.4) e o comportamento comum.

Cada recurso declara modelo, escopo minimo, campos expostos, filtros e busca. O
``RecursoDaApi`` aplica o escopo do token, o recorte de unidade, paginacao, filtros,
``updated_since``/``deleted_since``, ``ETag``, ``Idempotency-Key``, ``dry_run`` e o
registro de auditoria por token -- sem repetir isso em cada viewset.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.auditoria import registrar

#: Campo usado para ETag e busca incremental quando o modelo nao tem ``atualizado_em``.
CAMPOS_DE_TEMPO = ("atualizado_em", "data_at_user", "criado_em", "data_create_user", "id")


@dataclass(frozen=True)
class Recurso:
    """Declaracao de um recurso exposto pela API."""

    slug: str
    modelo: str
    escopo: str
    campos: tuple = ()
    busca: tuple = ()
    filtros: tuple = ()
    ordenacao: tuple = ("-id",)
    somente_leitura: bool = False
    plataforma: bool = False
    sem_unidade: bool = False
    ajuda: str = ""


RECURSOS: tuple[Recurso, ...] = (
    # 1-5 plataforma
    Recurso("redes", "core.Rede", "plataforma", busca=("nome", "slug"), filtros=("status",),
            ordenacao=("nome",), plataforma=True, sem_unidade=True,
            ajuda="Criar rede dispara o provisionamento do cliente."),
    Recurso("pacotes", "plataforma.Pacote", "plataforma", filtros=("visivel_no_site",),
            ordenacao=("preco_mensal",), plataforma=True, sem_unidade=True),
    Recurso("assinaturas", "plataforma.Assinatura", "plataforma", filtros=("situacao", "pacote"),
            plataforma=True, sem_unidade=True),
    Recurso("faturas", "plataforma.Fatura", "plataforma", filtros=("situacao",),
            plataforma=True, sem_unidade=True),
    Recurso("metricas", "plataforma.MetricaDaPlataforma", "plataforma", plataforma=True,
            sem_unidade=True, somente_leitura=True),
    # 6-10 rede e operacao
    Recurso("unidades", "core.Unidade", "unidades", busca=("nome", "codigo", "cidade"),
            filtros=("status", "tipo", "uf"), ordenacao=("nome",), sem_unidade=True),
    Recurso("equipe", "core.VinculoUsuario", "equipe", filtros=("papel", "ativo", "unidade"),
            sem_unidade=True),
    Recurso("convites", "core.ConviteEquipe", "equipe", filtros=("status",), sem_unidade=True),
    Recurso("alunos", "usuarios.Usuario", "alunos", busca=("nome", "email_user", "cpf_cnpj_user"),
            filtros=("status_user", "unidade"), ordenacao=("nome",)),
    Recurso("matriculas", "financeiro.Pagamento", "financeiro", filtros=("status", "unidade", "plano"),
            ordenacao=("-data_pagamento",)),
    Recurso("contratos", "financeiro.Contrato", "financeiro", filtros=("status",),
            somente_leitura=False),
    Recurso("professores", "professores.Professor", "professores", busca=("nome", "email_prof"),
            filtros=("status_prof", "unidade"), ordenacao=("nome",)),
    Recurso("aulas", "aulas.Aulas", "aulas", busca=("nome",), filtros=("unidade",), ordenacao=("nome",)),
    Recurso("midias", "aulas.ImagemAula", "aulas", filtros=("aula",), somente_leitura=True),
    Recurso("turmas", "painel.Painel", "agenda", filtros=("unidade",), ordenacao=("nome",)),
    Recurso("agendamentos", "agendamento.Agendamento", "agenda", filtros=("status", "unidade", "painel"),
            ordenacao=("-data_agendamento",)),
    Recurso("presencas", "agendamento.Presenca", "agenda", filtros=("agendamento",),
            somente_leitura=True),
    Recurso("avaliacoes", "agendamento.AvaliacaoFisica", "saude", filtros=("usuario",),
            somente_leitura=False),
    Recurso("planos", "financeiro.Plano", "financeiro", busca=("nome",), filtros=("tipo", "unidade"),
            ordenacao=("nome",)),
    Recurso("cobrancas", "financeiro.Cobranca", "financeiro", filtros=("status", "unidade"),
            ordenacao=("-vencimento",)),
    Recurso("pagamentos", "financeiro.Pagamento", "financeiro", filtros=("status", "unidade"),
            ordenacao=("-data_pagamento",), somente_leitura=False),
    Recurso("despesas", "financeiro.Despesa", "financeiro", filtros=("categoria", "unidade"),
            ordenacao=("-data",)),
    Recurso("repasses", "rede.Repasse", "repasses", filtros=("situacao", "unidade"),
            ordenacao=("-inicio",), sem_unidade=True),
    Recurso("metas", "rede.Meta", "rede", filtros=("indicador", "unidade"), sem_unidade=True),
    Recurso("comunicados", "rede.Comunicado", "rede", filtros=("publico", "ativo"),
            ordenacao=("-criado_em",), sem_unidade=True),
    Recurso("templates", "notificacoes.TemplateMensagem", "comunicacao", busca=("nome",),
            filtros=("canal",), somente_leitura=False),
    Recurso("auditoria", "api.RegistroAuditoria", "auditoria", filtros=("recurso", "acao", "usuario"),
            ordenacao=("-criado_em",), somente_leitura=True, sem_unidade=True),
    Recurso("webhooks", "api.WebhookDeSaida", "webhooks", filtros=("estado",),
            ordenacao=("-criado_em",), sem_unidade=True),
    Recurso("tarefas", "api.TarefaAssincrona", "relatorios", filtros=("tipo", "situacao"),
            ordenacao=("-criado_em",), somente_leitura=True, sem_unidade=True),
    Recurso("tokens", "api.ApiToken", "rede", filtros=("ativo",), ordenacao=("-criado_em",),
            somente_leitura=False, sem_unidade=True,
            ajuda="O segredo aparece uma unica vez, na criacao ou na rotacao."),
)
#: Recursos que nao entram no router automatico (tem viewset proprio).
FORA_DO_ROUTER = {"metricas", "contratos", "presencas", "midias", "cobrancas"}

_CACHE_SERIALIZADORES: dict[tuple, type] = {}


def modelo_de(recurso: Recurso):
    return apps.get_model(recurso.modelo)


def campo_de_tempo(modelo) -> str:
    for nome in CAMPOS_DE_TEMPO:
        if any(campo.name == nome for campo in modelo._meta.get_fields()):
            return nome
    return "pk"


def serializador_de(recurso: Recurso) -> type:
    chave = (recurso.modelo, recurso.campos)
    if chave in _CACHE_SERIALIZADORES:
        return _CACHE_SERIALIZADORES[chave]
    modelo = modelo_de(recurso)

    class Serializador(serializers.ModelSerializer):
        class Meta:
            model = modelo
            fields = recurso.campos or "__all__"
            read_only_fields = (
                [campo.name for campo in modelo._meta.fields
                 if campo.name in {"criado_em", "atualizado_em", "arquivado_em", "id"}]
            )

    Serializador.__name__ = f"{modelo.__name__}DaApi"
    _CACHE_SERIALIZADORES[chave] = Serializador
    return Serializador


class RecursoDaApi(viewsets.ModelViewSet):
    """ViewSet generico: escopo, recorte, paginacao, filtros, ETag e idempotencia."""

    recurso: Recurso = None
    filtros_extras = ()

    # ------------------------------------------------------------ escopo e consulta
    def escopos_do_token(self) -> list[str]:
        token = getattr(self.request, "auth", None)
        if token is not None and hasattr(token, "escopos"):
            return list(token.escopos or [])
        if getattr(self.request.user, "is_authenticated", False) and self.request.user.is_staff:
            return ["*"]
        return ["*"] if getattr(self.request.user, "is_authenticated", False) else []

    def escopo_exigido(self, escrita: bool) -> str:
        sufixo = "write" if escrita else "read"
        base = "plataforma" if self.recurso.plataforma else self.recurso.escopo
        if self.recurso.plataforma:
            return f"plataforma:{sufixo}"
        if self.recurso.escopo == "auditoria":
            return "auditoria:read"
        if self.recurso.escopo == "relatorios":
            return "relatorios:read"
        if self.recurso.escopo == "webhooks":
            return "webhooks:write"
        return f"{base}:{sufixo}"

    def gerenciador(self):
        """Usa o manager escopado quando existe (TenantModel) e o padrao quando nao."""
        modelo = modelo_de(self.recurso)
        return getattr(modelo, "todos", None) or modelo._default_manager

    def get_serializer_class(self):
        return serializador_de(self.recurso)

    def get_queryset(self):
        from api.escopos import tem_escopo

        exigido = self.escopo_exigido(escrita=False)
        if not tem_escopo(self.escopos_do_token(), exigido):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(f"O token precisa de {exigido}.")
        consulta = self.gerenciador().all()
        campos = {campo.name for campo in consulta.model._meta.get_fields()}
        if "arquivado_em" in campos:
            consulta = consulta.filter(arquivado_em__isnull=True)

        rede = getattr(self.request, "rede", None) or getattr(
            getattr(self.request, "auth", None), "rede", None
        )
        if not self.recurso.plataforma and not self.recurso.sem_unidade and "rede" in campos and rede:
            consulta = consulta.filter(rede=rede)
        unidade = getattr(self.request, "unidade", None)
        if unidade is not None and "unidade" in campos and not self.recurso.sem_unidade:
            parametro = self.request.query_params.get("unidade")
            if parametro:
                consulta = consulta.filter(unidade_id=parametro)
            else:
                consulta = consulta.filter(Q(unidade=unidade) | Q(unidade__isnull=True))

        for filtro in self.recurso.filtros:
            valor = self.request.query_params.get(filtro)
            if valor not in (None, ""):
                consulta = consulta.filter(**{filtro: valor})

        busca = self.request.query_params.get("busca")
        if busca and self.recurso.busca:
            condicao = Q()
            for campo in self.recurso.busca:
                condicao |= Q(**{f"{campo}__icontains": busca})
            consulta = consulta.filter(condicao)

        campo_tempo = campo_de_tempo(consulta.model)
        for parametro in ("updated_since", "deleted_since"):
            valor = self.request.query_params.get(parametro)
            if valor and campo_tempo != "pk":
                quando = self._como_data(valor)
                consulta = consulta.filter(**{f"{campo_tempo}__gte": quando})

        ordenacao = self.request.query_params.get("ordering") or ",".join(self.recurso.ordenacao)
        permitidos = {campo.name for campo in consulta.model._meta.get_fields()} | {
            "pk", f"-pk", *self.recurso.ordenacao, *self.recurso.filtros}
        escolhidas = [item for item in ordenacao.split(",") if item.strip().lstrip("-") in permitidos]
        return consulta.order_by(*(escolhidas or self.recurso.ordenacao))

    @staticmethod
    def _como_data(valor: str):
        """Aceita ISO-8601 (o "+" do fuso pode chegar como espaco na query string)."""
        texto = valor.strip().replace("Z", "+00:00").replace(" ", "+")
        try:
            return datetime.fromisoformat(texto)
        except ValueError:
            from django.utils.dateparse import parse_datetime

            interpretado = parse_datetime(texto)
            if interpretado is None:
                raise ValueError(f"data invalida: {valor}") from None
            return interpretado

    def assinatura_do_resultado(self, consulta) -> str:
        campo_tempo = campo_de_tempo(consulta.model)
        agregado = consulta.aggregate(total=Max("pk"))
        ultimo = consulta.aggregate(quando=Max(campo_tempo))["quando"] if campo_tempo != "pk" else None
        return f'W/"{consulta.count()}-{agregado["total"]}-{ultimo}"'

    def list(self, request, *args, **kwargs):
        consulta = self.filter_queryset(self.get_queryset())
        etiqueta = self.assinatura_do_resultado(consulta)
        if request.headers.get("If-None-Match") == etiqueta:
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        pagina = self.paginate_queryset(consulta)
        alvo = pagina if pagina is not None else consulta
        resposta = self.get_paginated_response(self.get_serializer(alvo, many=True).data)             if pagina is not None else Response(self.get_serializer(alvo, many=True).data)
        resposta["ETag"] = etiqueta
        return resposta

    def retrieve(self, request, *args, **kwargs):
        objeto = self.get_object()
        etiqueta = f'W/"{objeto.pk}-{getattr(objeto, campo_de_tempo(type(objeto)), "")}"'
        if request.headers.get("If-None-Match") == etiqueta:
            return Response(status=status.HTTP_304_NOT_MODIFIED)
        resposta = Response(self.get_serializer(objeto).data)
        resposta["ETag"] = etiqueta
        return resposta

    # ------------------------------------------------------------ escrita
    def exigir_escrita(self):
        from api.escopos import tem_escopo

        exigido = self.escopo_exigido(escrita=True)
        return exigido, tem_escopo(self.escopos_do_token(), exigido)

    def dados_com_contexto(self, dados):
        """Acrescenta rede/unidade do contexto ANTES da validacao (campos obrigatorios do cliente)."""
        modelo = modelo_de(self.recurso)
        campos = {campo.name for campo in modelo._meta.get_fields()}
        copia = dict(dados or {})
        rede = getattr(self.request, "rede", None) or getattr(
            getattr(self.request, "auth", None), "rede", None)
        if "rede" in campos and not copia.get("rede") and rede is not None:
            copia["rede"] = rede.pk
        unidade = getattr(self.request, "unidade", None)
        if "unidade" in campos and not copia.get("unidade") and unidade is not None:
            copia["unidade"] = unidade.pk
        return copia

    def completar_contexto(self, serializador) -> None:
        """Preenche rede/unidade a partir do token quando o payload nao traz (escopo do cliente)."""
        modelo = modelo_de(self.recurso)
        campos = {campo.name for campo in modelo._meta.get_fields()}
        dados = getattr(serializador, "validated_data", {}) or {}
        rede = getattr(self.request, "rede", None) or getattr(
            getattr(self.request, "auth", None), "rede", None)
        if "rede" in campos and not dados.get("rede") and rede is not None:
            dados["rede"] = rede
        unidade = getattr(self.request, "unidade", None)
        if "unidade" in campos and not dados.get("unidade") and unidade is not None:
            dados["unidade"] = unidade

    #: metodo HTTP -> acao registrada na auditoria (compativel com a trilha da fase 1).
    ACOES_POR_METODO = {"POST": "criar", "PUT": "alterar", "PATCH": "alterar", "DELETE": "excluir"}

    def auditoria_da_escrita(self, registro, dados_depois=None) -> None:
        """Registra a escrita com o token que a fez (RF-API-008)."""
        token = getattr(self.request, "auth", None)
        entidade = self.recurso.slug[:-1] if self.recurso.slug.endswith("s") else self.recurso.slug
        acao = self.ACOES_POR_METODO.get(self.request.method.upper(), "ler")
        registrar(
            acao, entidade,
            entidade_id=getattr(registro, "pk", None),
            descricao=f"{self.request.method} {self.request.path}",
            request=self.request,
            token=token if hasattr(token, "pk") else None,
            dados_depois=dados_depois or {"id": getattr(registro, "pk", None)},
        )

    def create(self, request, *args, **kwargs):
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"type": "about:blank", "title": "Escopo insuficiente",
                             "status": 403, "detail": f"O token precisa de {exigido}.",
                             "codigo": "escopo_insuficiente"}, status=status.HTTP_403_FORBIDDEN)
        chave = request.headers.get("Idempotency-Key")
        if chave:
            guardado = cache.get(f"idem:{chave}")
            if guardado is not None:
                return Response(guardado["corpo"], status=guardado["status"],
                                headers={"Idempotency-Replayed": "true"})
        simular = str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}
        serializador = self.get_serializer(data=self.dados_com_contexto(request.data))
        serializador.is_valid(raise_exception=True)
        if simular:
            return Response(
                {"dry_run": True, "seria_criado": 1, "valido": True,
                 "dados": {chave: str(valor) for chave, valor in serializador.validated_data.items()}},
                status=status.HTTP_200_OK,
            )
        self.completar_contexto(serializador)
        registro = serializador.save()
        self.auditoria_da_escrita(registro)
        corpo = self.get_serializer(registro).data
        if chave:
            cache.set(f"idem:{chave}", {"corpo": corpo, "status": 201}, 60 * 60 * 24)
        return Response(corpo, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}.",
                             "codigo": "escopo_insuficiente"}, status=status.HTTP_403_FORBIDDEN)
        if str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}:
            return Response({"dry_run": True, "seria_atualizado": 1}, status=status.HTTP_200_OK)
        resposta = super().update(request, *args, **kwargs)
        if resposta.status_code < 400:
            self.auditoria_da_escrita(self.get_object())
        return resposta

    def destroy(self, request, *args, **kwargs):
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}.",
                             "codigo": "escopo_insuficiente"}, status=status.HTTP_403_FORBIDDEN)
        registro = self.get_object()
        if hasattr(registro, "arquivar"):
            registro.arquivar()          # exclusao vira arquivamento (RF-API-006)
            self.auditoria_da_escrita(registro)
            return Response(status=status.HTTP_204_NO_CONTENT)
        if hasattr(registro, "arquivado_em"):
            registro.arquivado_em = timezone.now()
            registro.save(update_fields=["arquivado_em"])
            self.auditoria_da_escrita(registro)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)

    # ------------------------------------------------------------ lote, previa e desfazer
    @action(detail=False, methods=["post"], url_path="lote")
    def lote(self, request):
        """Criacao/atualizacao em lote com relatorio por item (RF-API-011/005)."""
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}.",
                             "codigo": "escopo_insuficiente"}, status=status.HTTP_403_FORBIDDEN)
        itens = request.data if isinstance(request.data, list) else request.data.get("itens", [])
        simular = str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}
        atomico = str(request.query_params.get("atomic", "")).lower() in {"1", "true", "sim"}
        relatorio = {"dry_run": simular, "total": len(itens), "criados": 0, "erros": [], "criados_ids": []}
        if atomico:
            with transaction.atomic():
                self._processar_lote(itens, simular, relatorio, abortar_em_erro=True)
        else:
            self._processar_lote(itens, simular, relatorio)
        status_code = status.HTTP_200_OK if simular or relatorio["erros"] else status.HTTP_201_CREATED
        if not simular and relatorio["criados"]:
            registrar("criar_lote", self.recurso.slug, entidade_id=None,
                      descricao=f"{relatorio['criados']} registro(s) via lote "
                                f"({len(relatorio['criados_ids'])} id(s) para desfazer)",
                      request=request, token=getattr(request, "auth", None)
                      if hasattr(getattr(request, "auth", None), "pk") else None)
        return Response(relatorio, status=status_code)

    def _processar_lote(self, itens, simular, relatorio, abortar_em_erro=False):
        for indice, item in enumerate(itens):
            serializador = self.get_serializer(data=self.dados_com_contexto(item))
            if not serializador.is_valid():
                relatorio["erros"].append({"item": indice, "erros": serializador.errors})
                if abortar_em_erro:
                    raise serializers.ValidationError({"lote": relatorio["erros"]})
                continue
            if simular:
                relatorio["criados"] += 1
                continue
            self.completar_contexto(serializador)
            registro = serializador.save()
            relatorio["criados"] += 1
            relatorio["criados_ids"].append(getattr(registro, "pk", None))

    @action(detail=False, methods=["post"], url_path="desfazer")
    def desfazer(self, request):
        """Reverte um lote recente arquivando o que acabou de ser criado (RF-API-006)."""
        ids = request.data.get("ids", [])
        revertidos = 0
        for identificador in ids:
            registro = self.gerenciador().filter(pk=identificador).first()
            if registro is None:
                continue
            if hasattr(registro, "arquivado_em"):
                registro.arquivado_em = timezone.now()
                registro.save(update_fields=["arquivado_em"])
                revertidos += 1
        registrar("desfazer_lote", self.recurso.slug, entidade_id=None,
                  descricao=f"{revertidos} registro(s) revertido(s)", request=request)
        return Response({"revertidos": revertidos, "janela": "24h"})

# ------------------------------------------------------------------ recursos com acoes extras
class AlunoDaApi(RecursoDaApi):
    """Alunos: CRUD + ficha de saude, transferencia e inativacao (RF-API-010)."""

    recurso = next(item for item in RECURSOS if item.slug == "alunos")

    @action(detail=True, methods=["get"], url_path="ficha-saude")
    def ficha_saude(self, request, pk=None):
        from api.escopos import tem_escopo

        if not tem_escopo(self.escopos_do_token(), "saude:read"):
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": "A ficha de saude exige saude:read.",
                             "codigo": "escopo_insuficiente"}, status=status.HTTP_403_FORBIDDEN)
        aluno = self.get_object()
        ficha = getattr(aluno, "fichasaude", None)
        if ficha is None:
            return Response({"detail": "Aluno sem ficha de saude cadastrada."},
                            status=status.HTTP_404_NOT_FOUND)
        from governanca.servicos import registrar_acesso_sensivel

        registrar_acesso_sensivel(request.rede, aluno.nome, recurso="ficha_saude", acao="leitura",
                                  usuario=request.user if request.user.is_authenticated else None,
                                  origem="api")
        return Response({
            "aluno": aluno.nome, "altura": ficha.altura, "peso": ficha.peso,
            "restricoes": ficha.restricoes, "prescricoes": ficha.prescricoes,
            "usa_medicamento": ficha.usa_medicamento, "obs": ficha.obs,
        })

    @action(detail=True, methods=["post"], url_path="transferir")
    def transferir(self, request, pk=None):
        from rede.servicos import transferir_alunos

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."},
                            status=status.HTTP_403_FORBIDDEN)
        aluno = self.get_object()
        destino = self._unidade(request.data.get("unidade"))
        if destino is None:
            return Response({"title": "Unidade invalida", "status": 400,
                             "detail": "Informe a unidade de destino."}, status=status.HTTP_400_BAD_REQUEST)
        if str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}:
            return Response({"dry_run": True, "seria_transferido": 1,
                             "de": aluno.unidade_id, "para": destino.pk}, status=status.HTTP_200_OK)
        resultado = transferir_alunos([aluno], destino, request.data.get("motivo", ""), request.user)
        return Response(resultado, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="inativar")
    def inativar(self, request, pk=None):
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."},
                            status=status.HTTP_403_FORBIDDEN)
        aluno = self.get_object()
        if str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}:
            return Response({"dry_run": True, "seria_inativado": aluno.pk}, status=status.HTTP_200_OK)
        aluno.status_user = "Inativo"
        aluno.save(update_fields=["status_user"])
        self.auditoria_da_escrita(aluno)
        from api.webhooks import disparar_evento

        disparar_evento("aluno.inativado", {"aluno": aluno.pk, "nome": aluno.nome},
                        rede=getattr(request, "rede", None))
        return Response({"aluno": aluno.pk, "status": aluno.status_user}, status=status.HTTP_200_OK)

    def _unidade(self, identificador):
        from core.models import Unidade

        if not identificador:
            return None
        return Unidade.objects.filter(pk=identificador).first()


class UnidadeDaApi(RecursoDaApi):
    """Unidades: CRUD + encerramento e aplicacao de template (RF-RED-016/024)."""

    recurso = next(item for item in RECURSOS if item.slug == "unidades")

    @action(detail=True, methods=["post"], url_path="encerrar")
    def encerrar(self, request, pk=None):
        from core.models import Unidade
        from rede.servicos import ErroDeRede, encerrar_unidade

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        unidade = self.get_object()
        destino = Unidade.objects.filter(pk=request.data.get("destino")).first() if request.data.get("destino") else None
        if str(request.query_params.get("dry_run", "")).lower() in {"1", "true", "sim"}:
            from usuarios.models import Usuario

            return Response({"dry_run": True, "unidade": unidade.nome,
                             "alunos_a_transferir": Usuario.todos.filter(unidade=unidade).count(),
                             "destino": destino.pk if destino else None}, status=status.HTTP_200_OK)
        try:
            resultado = encerrar_unidade(unidade, destino, usuario=request.user)
        except ErroDeRede as erro:
            return Response({"title": "Operacao recusada", "status": 400, "detail": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(resultado, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="template")
    def template(self, request, pk=None):
        from rede.models import TemplateDeUnidade
        from rede.servicos import aplicar_template

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        unidade = self.get_object()
        modelo = TemplateDeUnidade.objects.filter(pk=request.data.get("template")).first()
        implantacao = aplicar_template(unidade, modelo, usuario=request.user)
        return Response({"unidade": unidade.pk, "template": getattr(modelo, "pk", None),
                         "progresso": implantacao.progresso,
                         "aplicado": implantacao.resultado.get("aplicado", [])},
                        status=status.HTTP_200_OK)


class RepasseDaApi(RecursoDaApi):
    """Repasses: lista/detalhe + calculo, emissao e baixa (RF-RED-012)."""

    recurso = next(item for item in RECURSOS if item.slug == "repasses")

    @action(detail=False, methods=["get"], url_path="calcular")
    def calcular(self, request):
        from core.models import Unidade
        from rede.servicos import ErroDeRede, calcular_repasse, periodo_do_mes

        unidade = Unidade.objects.filter(pk=request.query_params.get("unidade")).first()
        if unidade is None:
            return Response({"title": "Unidade obrigatoria", "status": 400,
                             "detail": "Informe ?unidade=<id>."}, status=status.HTTP_400_BAD_REQUEST)
        inicio, fim = periodo_do_mes()
        try:
            calculo = calcular_repasse(unidade, inicio, fim)
        except ErroDeRede as erro:
            return Response({"title": "Sem regra de repasse", "status": 400, "detail": str(erro)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"unidade": unidade.nome, "inicio": inicio, "fim": fim,
                         "base_de_calculo": str(calculo["base_de_calculo"]),
                         "valor_devido": str(calculo["valor_devido"]),
                         "linhas": [{"descricao": linha["descricao"], "valor": str(linha["valor"])}
                                    for linha in calculo["linhas"]]})

    @action(detail=True, methods=["post"], url_path="emitir")
    def emitir(self, request, pk=None):
        from rede.servicos import emitir_repasse, periodo_do_mes

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        previsto = self.get_object()
        repasse = emitir_repasse(previsto.unidade, previsto.inicio, previsto.fim, request.user,
                                 forcar=True)
        from api.webhooks import disparar_evento

        disparar_evento("repasse.emitido", {"repasse": repasse.pk, "unidade": repasse.unidade_id,
                                            "valor": str(repasse.valor_devido)},
                        rede=getattr(request, "rede", None))
        return Response({"repasse": repasse.pk, "situacao": repasse.situacao,
                         "valor_devido": str(repasse.valor_devido),
                         "hash": repasse.hash_do_calculo}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="baixar")
    def baixar(self, request, pk=None):
        from rede.servicos import marcar_repasse_pago

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        repasse = self.get_object()
        marcar_repasse_pago(repasse, request.data.get("valor") or repasse.saldo, request.user)
        repasse.refresh_from_db()
        return Response({"repasse": repasse.pk, "situacao": repasse.situacao,
                         "saldo": str(repasse.saldo)}, status=status.HTTP_200_OK)


class MetaDaApi(RecursoDaApi):
    recurso = next(item for item in RECURSOS if item.slug == "metas")

    @action(detail=True, methods=["get"], url_path="acompanhamento")
    def acompanhamento(self, request, pk=None):
        from rede.servicos import calcular_realizado

        meta = self.get_object()
        realizado = calcular_realizado(meta)
        return Response({"meta": meta.pk, "indicador": meta.indicador, "alvo": str(meta.alvo),
                         "realizado": str(realizado), "atingida": realizado >= meta.alvo})


class ComunicadoDaApi(RecursoDaApi):
    recurso = next(item for item in RECURSOS if item.slug == "comunicados")

    @action(detail=True, methods=["post"], url_path="enviar")
    def enviar(self, request, pk=None):
        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        comunicado = self.get_object()
        from core.models import Unidade

        unidades = Unidade.objects.filter(pk__in=comunicado.unidade_id and [comunicado.unidade_id]
                                          or list(Unidade.objects.filter(rede=comunicado.rede)
                                                  .values_list("pk", flat=True)))
        return Response({"comunicado": comunicado.pk, "unidades": unidades.count(),
                         "exigem_confirmacao": comunicado.exige_confirmacao,
                         "leituras": comunicado.leituras}, status=status.HTTP_200_OK)


class WebhookDaApi(RecursoDaApi):
    recurso = next(item for item in RECURSOS if item.slug == "webhooks")

    def perform_create(self, serializer):
        serializer.save(segredo=serializer.validated_data.get("segredo") or __import__(
            "api.models", fromlist=["WebhookDeSaida"]).WebhookDeSaida.gerar_segredo())

    @action(detail=True, methods=["get"], url_path="entregas")
    def entregas(self, request, pk=None):
        webhook = self.get_object()
        return Response([
            {"entrega": entrega.entrega, "evento": entrega.evento, "situacao": entrega.situacao,
             "tentativas": entrega.tentativas, "resposta": entrega.resposta,
             "proxima_tentativa": entrega.proxima_tentativa, "criado_em": entrega.criado_em}
            for entrega in webhook.entregas.all()[:100]
        ])

    @action(detail=True, methods=["post"], url_path="reenviar")
    def reenviar(self, request, pk=None):
        from api.webhooks import reenviar

        webhook = self.get_object()
        identificador = request.data.get("entrega")
        entrega = webhook.entregas.filter(entrega=identificador).first() if identificador else \
            webhook.entregas.exclude(situacao="entregue").first()
        if entrega is None:
            return Response({"title": "Nada para reenviar", "status": 404,
                             "detail": "Sem entregas pendentes."}, status=status.HTTP_404_NOT_FOUND)
        entrega = reenviar(entrega)
        return Response({"entrega": entrega.entrega, "situacao": entrega.situacao,
                         "tentativas": entrega.tentativas})


class TokenDaApi(RecursoDaApi):
    recurso = next(item for item in RECURSOS if item.slug == "tokens")

    def create(self, request, *args, **kwargs):
        from api.models import ApiToken

        exigido, permitido = self.exigir_escrita()
        if not permitido:
            return Response({"title": "Escopo insuficiente", "status": 403,
                             "detail": f"O token precisa de {exigido}."}, status=status.HTTP_403_FORBIDDEN)
        escopos = request.data.get("escopos") or []
        if not escopos:
            return Response({"title": "Escopos obrigatorios", "status": 400,
                             "detail": "Informe o menor conjunto de escopos necessarios (RF-API-004)."},
                            status=status.HTTP_400_BAD_REQUEST)
        token, segredo = ApiToken.gerar(
            rede=getattr(request, "rede", None), nome=request.data.get("nome", "token"),
            escopos=escopos, criado_por=request.user if request.user.is_authenticated else None,
        )
        registrar("criar", "tokens", entidade_id=token.pk,
                  descricao=f"Token {token.nome!r} criado com escopos {escopos}", request=request)
        return Response({"id": token.pk, "nome": token.nome, "escopos": token.escopos,
                         "segredo": segredo, "aviso": "O segredo aparece uma unica vez."},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="rotacionar")
    def rotacionar(self, request, pk=None):
        token = self.get_object()
        segredo = token.rotacionar()
        registrar("rotacionar", "tokens", entidade_id=token.pk,
                  descricao=f"Token {token.nome!r} rotacionado", request=request)
        return Response({"id": token.pk, "segredo": segredo,
                         "aviso": "Guarde agora: o segredo anterior parou de funcionar."})


class TarefaDaApi(RecursoDaApi):
    recurso = next(item for item in RECURSOS if item.slug == "tarefas")

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        from pathlib import Path as Caminho

        tarefa = self.get_object()
        if tarefa.situacao != tarefa.Situacao.CONCLUIDA or not tarefa.arquivo:
            return Response({"title": "Tarefa sem arquivo", "status": 409,
                             "detail": f"Situacao atual: {tarefa.get_situacao_display()}.",
                             "erro": tarefa.erro}, status=status.HTTP_409_CONFLICT)
        if tarefa.termina_em and tarefa.termina_em < timezone.now():
            return Response({"title": "Link expirado", "status": 410,
                             "detail": "Gere a tarefa novamente."}, status=status.HTTP_410_GONE)
        caminho = Caminho(tarefa.arquivo)
        if not caminho.exists():
            return Response({"title": "Arquivo indisponivel", "status": 404}, status=status.HTTP_404_NOT_FOUND)
        resposta = HttpResponse(caminho.read_bytes(), content_type="text/csv")
        resposta["Content-Disposition"] = f'attachment; filename="tarefa-{tarefa.pk}.csv"'
        return resposta


CLASSES = {
    "alunos": AlunoDaApi, "unidades": UnidadeDaApi, "repasses": RepasseDaApi,
    "metas": MetaDaApi, "comunicados": ComunicadoDaApi, "webhooks": WebhookDaApi,
    "tokens": TokenDaApi, "tarefas": TarefaDaApi,
}


def classe_de(recurso: Recurso) -> type:
    return CLASSES.get(recurso.slug) or type(
        f"{recurso.slug.title()}DaApi", (RecursoDaApi,), {"recurso": recurso}
    )


def montar_router():
    from rest_framework.routers import DefaultRouter

    router = DefaultRouter()
    for recurso in RECURSOS:
        if recurso.slug in FORA_DO_ROUTER:
            continue
        router.register(recurso.slug, classe_de(recurso), basename=recurso.slug)
    return router


router = montar_router()
