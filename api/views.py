"""Views de apoio da API: saude/estado da instalacao."""

from __future__ import annotations

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import EstadoSerializer, SessaoSerializer
from core.context import rede_atual, unidade_atual


class EstadoDaInstalacao(APIView):
    """Contrato usado antes de operar por automacao (RF-API-014).

    Sem autenticacao devolve o minimo (versao). Autenticado devolve tambem o
    contexto de rede/unidade e os escopos disponiveis.
    """

    permission_classes = [AllowAny]
    serializer_class = EstadoSerializer  # deixa o OpenAPI documentar a resposta

    def get(self, request):
        dados = {
            "versao_api": "1.0.0",
            "rede": None,
            "unidade": None,
            "status_rede": None,
            "escopos": [],
            "recursos": {},
        }
        if getattr(request.user, "is_authenticated", False) and not request.user.is_anonymous:
            rede = getattr(request, "rede", None) or rede_atual()
            unidade = getattr(request, "unidade", None) or unidade_atual()
            dados.update(
                {
                    "rede": getattr(rede, "slug", None),
                    "unidade": getattr(unidade, "nome", None),
                    "status_rede": getattr(rede, "status", None),
                    "escopos": sorted(getattr(request.user, "escopos", []) or []),
                    "recursos": {
                        "alunos": "alunos:read/alunos:write",
                        "professores": "professores:read/professores:write",
                        "aulas": "aulas:read/aulas:write",
                        "financeiro": "financeiro:read/financeiro:write",
                        "relatorios": "relatorios:read",
                        "webhooks": "webhooks:write",
                    },
                }
            )
        return Response(EstadoSerializer(dados).data)


class MinhaSessao(APIView):
    """Quem sou eu nesta chamada (usado pelo Hermes para validar o token)."""

    permission_classes = [IsAuthenticated]
    serializer_class = SessaoSerializer

    def get(self, request):
        usuario = request.user
        return Response(
            {
                "identidade": str(usuario),
                "tipo": "token" if hasattr(usuario, "escopos") else "usuario",
                "escopos": sorted(getattr(usuario, "escopos", []) or []),
                "rede": getattr(getattr(request, "rede", None) or rede_atual(), "slug", None),
                "unidade": getattr(
                    getattr(request, "unidade", None) or unidade_atual(), "nome", None
                ),
            }
        )
