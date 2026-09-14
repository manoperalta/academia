"""Valores de integracao de terceiros por rede."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TenantModel
from integracoes import catalogo


class IntegracaoDaRede(TenantModel):
    """Os valores que um provedor de terceiro entregou para uma rede.

    Os valores ficam em ``campos`` (JSON) porque cada provedor entrega um conjunto proprio --
    e o catalogo evolui sem migracao a cada provedor novo. Segredo guardado aqui nunca volta
    para a tela: quem precisa do valor real (cobranca, NFS-e) le pelo servico.
    """

    provedor = models.CharField("provedor", max_length=40, db_index=True)
    ativo = models.BooleanField("ativa", default=False)
    campos = models.JSONField("valores recebidos", default=dict, blank=True)
    arquivo = models.FileField(
        "arquivo enviado",
        upload_to="integracoes/",
        blank=True,
        help_text="Certificado ou arquivo que o provedor entrega (o nome fica junto dos valores).",
    )
    observacoes = models.TextField("observacoes", blank=True)
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)
    atualizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integracoes_atualizadas",
        verbose_name="atualizada por",
    )

    class Meta:
        verbose_name = "Integracao da rede"
        verbose_name_plural = "Integracoes da rede"
        ordering = ("provedor",)
        constraints = [
            models.UniqueConstraint(fields=["rede", "provedor"], name="integracao_unica_por_rede")
        ]

    def __str__(self) -> str:
        return f"{catalogo.obter(self.provedor).nome if catalogo.obter(self.provedor) else self.provedor}"

    def clean(self) -> None:
        """Provedor precisa existir no catalogo (e ele que diz quais campos existem)."""
        if catalogo.obter(self.provedor) is None:
            raise ValidationError({"provedor": "Provedor desconhecido no catalogo de integracoes."})

    @property
    def nome_do_provedor(self) -> str:
        integracao = catalogo.obter(self.provedor)
        return integracao.nome if integracao else self.provedor

    @property
    def valor_real(self) -> dict:
        return dict(self.campos or {})
