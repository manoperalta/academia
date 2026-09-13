from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TenantModel
from core.validadores import validar_imagem_de_capa


class Professor(TenantModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="professor_profile",
        null=True,
        blank=True,
    )

    STATUS_CHOICES = (
        ("Ativo", "Ativo"),
        ("Inativo", "Inativo"),
    )

    nome = models.CharField(max_length=255, verbose_name="Nome Completo")
    data_nasc = models.DateField(verbose_name="Data de Nascimento", null=True, blank=True)
    endereco_prof = models.CharField(max_length=255, verbose_name="Endereço", null=True, blank=True)
    numero_end_prof = models.CharField(max_length=20, verbose_name="Número", null=True, blank=True)
    bairro_prof = models.CharField(max_length=100, verbose_name="Bairro", null=True, blank=True)
    cep_prof = models.CharField(max_length=20, verbose_name="CEP", null=True, blank=True)
    cpf_cnpj_prof = models.CharField(max_length=20, verbose_name="CPF/CNPJ", null=True, blank=True)
    email_prof = models.EmailField(verbose_name="E-mail", blank=True, null=True)
    telefone_prof = models.CharField(max_length=20, verbose_name="Telefone", blank=True, null=True)
    data_create_prof = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_prof = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    foto_prof = models.ImageField(
        upload_to="professores_fotos/",
        null=True,
        blank=True,
        verbose_name="Foto de Perfil",
        validators=[validar_imagem_de_capa],
        help_text="png, jpeg ou webp ate 5 MB. E a foto que o aluno ve ao escolher o professor.",
    )
    status_prof = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="Ativo", verbose_name="Status"
    )

    def __str__(self):
        return self.nome

    # ------------------------------------------------------------------ valor da hora
    @property
    def regra_do_valor_por_hora(self):
        """Regra ``por_hora`` vigente deste professor (a fonte unica do quanto ele recebe)."""
        from remuneracao.models import RegraDeComissao, TipoDeComissao

        regras = RegraDeComissao.objects.filter(
            rede=self.rede, professor=self, tipo=TipoDeComissao.POR_HORA, ativo=True
        ).order_by("-criado_em")
        hoje = timezone.localdate()
        return next((regra for regra in regras if regra.vale_em(hoje)), None)

    @property
    def valor_por_hora(self):
        """Valor da hora em reais (``None`` quando ainda nao foi definido no painel)."""
        regra = self.regra_do_valor_por_hora
        return regra.valor if regra is not None else None

    def definir_valor_por_hora(self, valor, *, vigencia=None, usuario=None):
        """Define o valor da hora do professor, encerrando a regra anterior.

        Historico em vez de sobrescrita: a regra anterior fica com vigencia encerrada e a nova
        nasce hoje -- assim a comissao de meses passados continua reproduzivel. Quem chama e o
        painel do admin da rede / gestor da unidade.
        """
        from remuneracao.models import RegraDeComissao, TipoDeComissao

        hoje = vigencia or timezone.localdate()
        RegraDeComissao.objects.filter(
            rede=self.rede, professor=self, tipo=TipoDeComissao.POR_HORA, ativo=True
        ).update(ativo=False, fim_vigencia=hoje - timedelta(days=1))
        regra = RegraDeComissao.objects.create(
            rede=self.rede,
            unidade=self.unidade,
            professor=self,
            tipo=TipoDeComissao.POR_HORA,
            valor=valor,
            inicio_vigencia=hoje,
            descricao="Valor por hora definido no painel",
        )
        from api.auditoria import registrar

        registrar(
            "valor_por_hora",  # a coluna de acao aceita 20 caracteres
            "professor",
            entidade_id=self.pk,
            descricao=f"Valor por hora de {self.nome} definido em R$ {valor}",
        )
        return regra

    class Meta:
        verbose_name = "Professor"
        verbose_name_plural = "Professores"
