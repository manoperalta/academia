"""Serializers da API.

Regra de seguranca: ``rede`` e ``unidade`` sao SEMPRE somente leitura -- o
cliente nao escolhe tenant, o contexto decide (PRD 12.2, "tenant_id forjado").
"""

from __future__ import annotations

from rest_framework import serializers

from api.models import ApiToken, RegistroAuditoria
from aulas.models import Aulas
from core.models import Rede, Unidade, VinculoUsuario
from financeiro.models import Pagamento, Plano
from professores.models import Professor
from usuarios.models import Usuario

CAMPOS_PROTEGIDOS = ("id", "rede", "unidade", "arquivado_em", "criado_em", "atualizado_em")


class RedeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rede
        fields = [
            "id",
            "nome",
            "slug",
            "cnpj",
            "email_responsavel",
            "telefone",
            "dominio",
            "status",
            "trial_termina_em",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class UnidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidade
        fields = [
            "id",
            "rede",
            "nome",
            "codigo",
            "tipo",
            "cnpj",
            "endereco",
            "cidade",
            "uf",
            "telefone",
            "gestor",
            "status",
            "sobrescrever_branding",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "rede", "criado_em", "atualizado_em"]


class VinculoUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = VinculoUsuario
        fields = ["id", "usuario", "rede", "unidade", "papel", "ativo", "criado_em"]
        read_only_fields = ["id", "rede", "criado_em"]


class AlunoSerializer(serializers.ModelSerializer):
    """Perfil de aluno. Ficha de saude tem escopo proprio (``saude:read``)."""

    nome = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Usuario
        fields = "__all__"
        read_only_fields = (*CAMPOS_PROTEGIDOS, "user")


class ProfessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Professor
        fields = "__all__"
        read_only_fields = (*CAMPOS_PROTEGIDOS, "user")


class AulaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aulas
        fields = "__all__"
        read_only_fields = CAMPOS_PROTEGIDOS


class PlanoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plano
        fields = "__all__"
        read_only_fields = CAMPOS_PROTEGIDOS


class PagamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pagamento
        fields = "__all__"
        read_only_fields = CAMPOS_PROTEGIDOS


class ApiTokenSerializer(serializers.ModelSerializer):
    """Token nunca devolve o segredo (so na criacao, pelo campo ``credencial``)."""

    credencial = serializers.CharField(read_only=True)

    class Meta:
        model = ApiToken
        fields = [
            "id",
            "nome",
            "prefixo",
            "rede",
            "unidade",
            "escopos",
            "ativo",
            "expira_em",
            "ultimo_uso_em",
            "ultimo_ip",
            "criado_em",
            "revogado_em",
            "credencial",
        ]
        read_only_fields = [
            "id",
            "prefixo",
            "ultimo_uso_em",
            "ultimo_ip",
            "criado_em",
            "revogado_em",
        ]


class AuditoriaSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source="usuario.get_username", read_only=True)

    class Meta:
        model = RegistroAuditoria
        fields = [
            "id",
            "rede",
            "unidade",
            "usuario",
            "usuario_nome",
            "acao",
            "entidade",
            "entidade_id",
            "descricao",
            "pedido_origem",
            "ip",
            "criado_em",
        ]
        read_only_fields = fields


class EstadoSerializer(serializers.Serializer):
    """Resposta de ``/api/v1/estado/`` (usada antes de operar por automacao)."""

    versao_api = serializers.CharField()
    rede = serializers.CharField(allow_null=True)
    unidade = serializers.CharField(allow_null=True)
    status_rede = serializers.CharField(allow_null=True)
    escopos = serializers.ListField(child=serializers.CharField())
    recursos = serializers.DictField()


class SessaoSerializer(serializers.Serializer):
    """Quem sou eu nesta chamada (usado pelo Hermes antes de operar)."""

    identidade = serializers.CharField()
    tipo = serializers.CharField()
    escopos = serializers.ListField(child=serializers.CharField())
    rede = serializers.CharField(allow_null=True)
    unidade = serializers.CharField(allow_null=True)
