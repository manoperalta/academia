"""ViewSets da API (CBV/DRF, sem regra de negocio na view).

Ponto critico: o queryset e resolvido **por requisicao** (``get_queryset``),
nunca guardado no atributo de classe -- guardar ``Model.objects.all()`` como
atributo congela o escopo do momento do import e desliga o isolamento. O escopo
de rede vem do manager (``objects`` respeita o contexto) e o recorte de unidade
e aplicado aqui.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api import serializers
from api.auditoria import registrar
from api.models import ApiToken, RegistroAuditoria
from api.permissions import EscopoNecessario, RedeNoContexto
from aulas.models import Aulas
from core.context import rede_atual, unidade_atual
from core.models import Rede, Unidade, VinculoUsuario
from financeiro.models import Pagamento, Plano
from professores.models import Professor
from usuarios.models import Usuario


class BaseViewSet(viewsets.ModelViewSet):
    """Base com escopo por requisicao, auditoria de escrita e recorte de unidade."""

    permission_classes = [IsAuthenticated, RedeNoContexto, EscopoNecessario]
    escopo_recurso = ""

    #: Modelo base do recurso (o queryset e montado por requisicao).
    modelo = None

    #: ViewSets de dado operacional recortam por unidade; cadastros de rede nao.
    recortar_por_unidade = True

    def get_queryset(self):
        if self.modelo is None:  # pragma: no cover - erro de programacao
            raise NotImplementedError("Defina 'modelo' no ViewSet.")
        queryset = self.modelo.objects.all()
        unidade = getattr(self.request, "unidade", None) or unidade_atual()
        if unidade is not None and self.recortar_por_unidade:
            queryset = queryset.filter(Q(unidade=unidade) | Q(unidade__isnull=True))
        return queryset

    # -- escrita ------------------------------------------------------------
    def dados_de_criacao(self) -> dict:
        """Campos que o cliente NAO informa: vem do contexto (nunca do payload)."""
        return {}

    def perform_create(self, serializer):
        instancia = serializer.save(**self.dados_de_criacao())
        registrar(
            RegistroAuditoria.Acao.CRIAR,
            self.basename,
            entidade_id=instancia.pk,
            descricao=f"Criado via API ({self.request.method})",
            dados_depois=self._resumo(instancia),
            request=self.request,
        )

    def perform_update(self, serializer):
        antes = self._resumo(serializer.instance)
        instancia = serializer.save()
        registrar(
            RegistroAuditoria.Acao.ALTERAR,
            self.basename,
            entidade_id=instancia.pk,
            descricao="Alterado via API",
            dados_antes=antes,
            dados_depois=self._resumo(instancia),
            request=self.request,
        )

    def perform_destroy(self, instance):
        """Exclusao de negocio e arquivamento (PRD 22.1 / RF-DSH-004)."""
        if hasattr(instance, "arquivar"):
            instance.arquivar()
        else:  # pragma: no cover - modelo sem soft delete
            instance.delete()
        registrar(
            RegistroAuditoria.Acao.ARQUIVAR,
            self.basename,
            entidade_id=instance.pk,
            descricao="Arquivado via API",
            request=self.request,
        )

    @staticmethod
    def _resumo(instancia) -> dict:
        dados = {}
        for campo in ("id", "nome", "rede_id", "unidade_id", "arquivado_em"):
            if hasattr(instancia, campo):
                valor = getattr(instancia, campo)
                dados[campo] = str(valor) if valor is not None else None
        return dados

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        """Restaura um registro arquivado."""
        instancia = self.get_object()
        if hasattr(instancia, "restaurar"):
            instancia.restaurar()
            registrar(
                RegistroAuditoria.Acao.RESTAURAR,
                self.basename,
                entidade_id=pk,
                descricao="Restaurado via API",
                request=request,
            )
        return Response(self.get_serializer(instancia).data)


class EscopoDaRedeMixin:
    """Recursos de cadastro da rede: a plataforma (superusuario) ve todas as redes."""

    recortar_por_unidade = False
    usa_todos = True

    def _queryset_base(self):
        raise NotImplementedError

    def get_queryset(self):
        usuario = self.request.user
        if getattr(usuario, "is_superuser", False) or getattr(usuario, "escopos", None):
            return self._queryset_base()
        rede = rede_atual()
        if rede is None:
            return self._queryset_base().none()
        return self._queryset_base().filter(rede=rede)


class RedeViewSet(BaseViewSet):
    modelo = Rede
    serializer_class = serializers.RedeSerializer
    escopo_recurso = "rede"
    recortar_por_unidade = False
    search_fields = ["nome", "slug", "cnpj"]
    filterset_fields = ["status"]
    ordering_fields = ["nome", "criado_em"]

    def get_queryset(self):
        usuario = self.request.user
        if getattr(usuario, "is_superuser", False) or getattr(usuario, "escopos", None):
            return Rede.todos.all()
        rede = rede_atual()
        return Rede.todos.filter(pk=rede.pk) if rede else Rede.todos.none()


class UnidadeViewSet(BaseViewSet):
    modelo = Unidade
    serializer_class = serializers.UnidadeSerializer
    escopo_recurso = "unidades"
    recortar_por_unidade = False
    search_fields = ["nome", "codigo", "cidade"]
    filterset_fields = ["tipo", "status", "rede"]
    ordering_fields = ["nome", "criado_em"]

    def get_queryset(self):
        usuario = self.request.user
        if getattr(usuario, "is_superuser", False) or getattr(usuario, "escopos", None):
            return Unidade.todos.all()
        rede = rede_atual()
        return Unidade.todos.filter(rede=rede) if rede else Unidade.todos.none()

    def dados_de_criacao(self) -> dict:
        return {"rede": rede_atual()}


class VinculoUsuarioViewSet(BaseViewSet):
    modelo = VinculoUsuario
    serializer_class = serializers.VinculoUsuarioSerializer
    escopo_recurso = "equipe"
    recortar_por_unidade = False
    filterset_fields = ["papel", "ativo", "rede", "unidade"]
    search_fields = ["usuario__username", "usuario__email"]

    def get_queryset(self):
        rede = rede_atual()
        return VinculoUsuario.todos.filter(rede=rede) if rede else VinculoUsuario.todos.none()

    def dados_de_criacao(self) -> dict:
        return {"rede": rede_atual()}


class AlunoViewSet(BaseViewSet):
    modelo = Usuario
    serializer_class = serializers.AlunoSerializer
    escopo_recurso = "alunos"
    filterset_fields = ["unidade", "rede"]
    search_fields = ["user__username", "user__first_name", "user__email"]
    ordering_fields = ["id", "criado_em"]


class ProfessorViewSet(BaseViewSet):
    modelo = Professor
    serializer_class = serializers.ProfessorSerializer
    escopo_recurso = "professores"
    filterset_fields = ["unidade", "rede"]
    search_fields = ["user__username", "user__first_name"]


class AulaViewSet(BaseViewSet):
    modelo = Aulas
    serializer_class = serializers.AulaSerializer
    escopo_recurso = "aulas"
    filterset_fields = ["unidade", "rede"]
    search_fields = ["nome", "descricao"]


class PlanoViewSet(BaseViewSet):
    modelo = Plano
    serializer_class = serializers.PlanoSerializer
    escopo_recurso = "financeiro"


class PagamentoViewSet(BaseViewSet):
    modelo = Pagamento
    serializer_class = serializers.PagamentoSerializer
    escopo_recurso = "financeiro"
    filterset_fields = ["unidade", "rede"]


class ApiTokenViewSet(BaseViewSet):
    modelo = ApiToken
    serializer_class = serializers.ApiTokenSerializer
    escopo_recurso = "rede"
    recortar_por_unidade = False

    def get_queryset(self):
        rede = rede_atual()
        return ApiToken.objects.filter(rede=rede) if rede else ApiToken.objects.none()

    def create(self, request, *args, **kwargs):
        """Cria o token e devolve a credencial UMA unica vez."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token, credencial = ApiToken.gerar(
            nome=serializer.validated_data.get("nome", "token"),
            rede=rede_atual(),
            unidade=serializer.validated_data.get("unidade"),
            escopos=serializer.validated_data.get("escopos", []),
            expira_em=serializer.validated_data.get("expira_em"),
            criado_por=request.user if getattr(request.user, "pk", None) else None,
        )
        registrar(
            RegistroAuditoria.Acao.CRIAR,
            "apitoken",
            entidade_id=token.pk,
            descricao=f"Token criado: {token.nome}",
            request=request,
        )
        dados = self.get_serializer(token).data
        dados["credencial"] = credencial
        dados["aviso"] = "Guarde agora: o segredo nao e exibido novamente."
        return Response(dados, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def rotacionar(self, request, pk=None):
        token = self.get_object()
        credencial = token.rotacionar()
        registrar(
            RegistroAuditoria.Acao.ALTERAR,
            "apitoken",
            entidade_id=token.pk,
            descricao="Token rotacionado",
            request=request,
        )
        return Response({"credencial": credencial, "prefixo": token.prefixo})

    @action(detail=True, methods=["post"])
    def revogar(self, request, pk=None):
        token = self.get_object()
        token.ativo = False
        token.revogado_em = timezone.now()
        token.save(update_fields=["ativo", "revogado_em"])
        registrar(
            RegistroAuditoria.Acao.ALTERAR,
            "apitoken",
            entidade_id=token.pk,
            descricao="Token revogado",
            request=request,
        )
        return Response({"detail": "Token revogado."})


class AuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.AuditoriaSerializer
    permission_classes = [IsAuthenticated, EscopoNecessario]
    escopo_recurso = "auditoria"
    filterset_fields = ["acao", "entidade", "rede", "unidade"]
    ordering_fields = ["criado_em"]
    search_fields = ["entidade", "entidade_id", "descricao"]

    def get_queryset(self):
        queryset = RegistroAuditoria.objects.all()
        usuario = self.request.user
        if getattr(usuario, "is_superuser", False) or getattr(usuario, "escopos", None):
            return queryset
        rede = rede_atual()
        return queryset.filter(rede=rede) if rede else queryset.none()
