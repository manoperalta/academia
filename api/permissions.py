"""Permissoes de API: escopo exigido por acao + escopo da rede."""

from __future__ import annotations

from rest_framework import permissions

from core.context import rede_atual


class EscopoNecessario(permissions.BasePermission):
    """Exige o escopo declarado **no view** (``escopo_recurso``/``escopos_por_acao``).

    Atencao: a instancia da permissao nao conhece o view -- por isso os atributos
    sao lidos de ``view``, nunca de ``self``. (Foi exatamente esse engano que fez
    a API aceitar escrita com token somente-leitura ate o teste pegar.)

    Exemplo::

        class AlunoViewSet(BaseViewSet):
            escopo_recurso = "alunos"
            escopos_por_acao = {"create": "alunos:write", "list": "alunos:read"}
    """

    message = "O token nao tem escopo para esta operacao."

    def has_permission(self, request, view):
        usuario = getattr(request, "user", None)
        if not usuario or not usuario.is_authenticated:
            return False

        # Usuario humano (sessao/JWT): o papel no vinculo decide (core.mixins).
        if not hasattr(usuario, "tem_escopo"):
            return True

        if "*" in (getattr(usuario, "escopos", None) or set()):
            return True

        escopo_recurso = getattr(view, "escopo_recurso", "")
        escopos_por_acao = getattr(view, "escopos_por_acao", {}) or {}
        exigido = escopos_por_acao.get(getattr(view, "action", None))
        if exigido is None and escopo_recurso:
            leitura = request.method in permissions.SAFE_METHODS
            exigido = f"{escopo_recurso}:{'read' if leitura else 'write'}"

        if exigido and not usuario.tem_escopo(exigido):
            self.message = (
                f"Token sem o escopo '{exigido}'. "
                f"Escopos deste token: {sorted(getattr(usuario, 'escopos', []) or [])}."
            )
            return False
        return True


class RedeNoContexto(permissions.BasePermission):
    """Garante que existe rede resolvida antes de tocar em dado de negocio."""

    message = "Nao foi possivel identificar a academia desta chamada."

    def has_permission(self, request, view):
        return getattr(request, "rede", None) is not None or rede_atual() is not None
