from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from core.models import TenantModel
from core.validadores import EXTENSOES_DE_VIDEO, validar_imagem_de_capa, validar_video_de_aula


class Aulas(TenantModel):
    CATEGORIAS_EXERCICIOS = [
        ("aerobico", "Aeróbico/Cardiovascular"),
        ("forca", "Treinamento de Força"),
        ("flexibilidade", "Flexibilidade/Alongamento"),
        ("neuromotor", "Equilíbrio e Coordenação"),
        ("pilates_solo", "Pilates Solo (Mat)"),
        ("pilates_aparelhos", "Pilates em Aparelhos"),
    ]

    RESTRICOES_CHOICES = [
        ("nenhuma", "Nenhuma"),
        ("cardiaco", "Problemas Cardíacos"),
        ("respiratorio", "Problemas Respiratórios"),
        ("coluna", "Problemas de Coluna"),
        ("articulacao", "Problemas Articulares"),
        ("gestante", "Gestante"),
        ("hipertensao", "Hipertensão"),
        ("lesao_muscular", "Lesão Muscular"),
        ("diabetes", "Diabetes"),
        ("obesidade", "Obesidade"),
    ]

    nome = models.CharField(max_length=255, verbose_name="Nome da Aula")
    descricao = models.TextField(verbose_name="Descrição")
    file_de_video = models.FileField(
        upload_to="videos_aulas/",
        null=True,
        blank=True,
        verbose_name="Arquivo de Vídeo",
        validators=[
            FileExtensionValidator(allowed_extensions=list(EXTENSOES_DE_VIDEO)),
            validar_video_de_aula,
        ],
        help_text=(
            "Video de atividade de ate 450 MB (mp4, webm, ogg, mkv, mov ou avi). "
            "Para arquivo grande, use o envio em partes do painel de midia."
        ),
    )
    # Para imagens, utilizaremos um modelo relacionado para permitir múltiplas imagens (até 5)
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Professor/Criador"
    )
    categorias_exercicios = models.CharField(
        max_length=50, choices=CATEGORIAS_EXERCICIOS, verbose_name="Categoria"
    )
    restricao = models.CharField(
        max_length=50,
        choices=RESTRICOES_CHOICES,
        default="nenhuma",
        verbose_name="Restrição de Saúde",
    )
    data_create_aula = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_aula = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    def __str__(self):
        return self.nome

    @property
    def duracao_em_minutos(self) -> int | None:
        """Duracao conhecida do video em minutos (``None`` quando o arquivo nao foi processado).

        O requisito pede que a soma dos videos feche o tempo do compromisso. Sem ffmpeg a duracao so
        existe quando o arquivo foi enviado pelo envio em partes (que grava a informacao do
        container); nesse caso a conta e mostrada, no outro a tela nao inventa numero.
        """
        for arquivo in self.midias_enviadas.all():
            if arquivo.duracao_segundos:
                return max(1, round(arquivo.duracao_segundos / 60))
        return None

    @property
    def capa(self):
        """Primeira capa cadastrada (o que o aluno ve antes de agendar)."""
        return self.imagens.order_by("pk").first()

    class Meta:
        verbose_name = "Aula"
        verbose_name_plural = "Aulas"


class ImagemAula(TenantModel):
    aula = models.ForeignKey(Aulas, related_name="imagens", on_delete=models.CASCADE)
    imagem = models.ImageField(
        upload_to="imagens_aulas/",
        validators=[validar_imagem_de_capa],
        help_text="Capa da aula: png, jpeg ou webp ate 5 MB.",
    )

    def __str__(self):
        return f"Imagem de {self.aula.nome}"
