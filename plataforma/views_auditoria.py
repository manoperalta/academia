"""Auditoria da plataforma: a trilha do que aconteceu, por rede e por operador.

Fica em arquivo proprio para nao mexer no views.py ja publicado do painel da plataforma: o modulo
apenas importa esta view e aponta a rota.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.views.generic import ListView

from plataforma.mixins import PlataformaMixin


class AuditoriaDaPlataformaView(PlataformaMixin, ListView):
    """Trilha somente de inclusao: quem fez o que, quando, em qual rede e de qual IP."""

    template_name = "plataforma/auditoria.html"
    context_object_name = "registros"
    paginate_by = 100

    def get_queryset(self):
        from api.models import RegistroAuditoria

        consulta = RegistroAuditoria.objects.select_related("rede", "unidade", "usuario").order_by(
            "-pk"
        )
        acao = self.request.GET.get("acao", "").strip()
        rede = self.request.GET.get("rede", "").strip()
        if acao:
            consulta = consulta.filter(acao=acao)
        if rede:
            consulta = consulta.filter(rede__nome__icontains=rede)
        return consulta

    def get(self, request, *args, **kwargs):
        if request.GET.get("formato") == "csv":
            import csv

            resposta = HttpResponse(content_type="text/csv")
            resposta["Content-Disposition"] = 'attachment; filename="auditoria-plataforma.csv"'
            escritor = csv.writer(resposta)
            escritor.writerow(
                ["quando", "operador", "acao", "rede", "unidade", "entidade", "entidade_id", "ip"]
            )
            for registro in self.get_queryset()[:5000]:
                escritor.writerow(
                    [
                        registro.criado_em.isoformat()
                        if getattr(registro, "criado_em", None)
                        else "",
                        str(getattr(registro, "usuario", "") or "sistema"),
                        registro.get_acao_display(),
                        getattr(getattr(registro, "rede", None), "nome", "") or "",
                        str(getattr(getattr(registro, "unidade", None), "nome", "") or ""),
                        getattr(registro, "entidade", "") or "",
                        getattr(registro, "entidade_id", "") or "",
                        getattr(registro, "endereco_ip", "") or "",
                    ]
                )
            return resposta
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from api.models import RegistroAuditoria

        contexto = super().get_context_data(**kwargs)
        contexto["total"] = self.get_queryset().count()
        contexto["acoes"] = RegistroAuditoria.Acao.choices
        contexto["filtro_acao"] = self.request.GET.get("acao", "")
        contexto["filtro_rede"] = self.request.GET.get("rede", "")
        return contexto
