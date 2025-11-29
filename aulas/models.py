from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator

class Aulas(models.Model):
    CATEGORIAS_EXERCICIOS = [
        ("aerobico", "Aeróbico/Cardiovascular"),
        ("forca", "Treinamento de Força"),
        ("flexibilidade", "Flexibilidade/Alongamento"),
        ("neuromotor", "Equilíbrio e Coordenação"),
        ("pilates_solo", "Pilates Solo (Mat)"),
        ("pilates_aparelhos", "Pilates em Aparelhos")
    ]

    nome = models.CharField(max_length=255, verbose_name="Nome da Aula")
    descricao = models.TextField(verbose_name="Descrição")
    file_de_video = models.FileField(
        upload_to='videos_aulas/', 
        null=True, 
        blank=True, 
        verbose_name="Arquivo de Vídeo",
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'ogg', 'mkv', 'mov', 'avi'])]
    )
    # Para imagens, utilizaremos um modelo relacionado para permitir múltiplas imagens (até 5)
    professor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Professor/Criador")
    categorias_exercicios = models.CharField(max_length=50, choices=CATEGORIAS_EXERCICIOS, verbose_name="Categoria")
    data_create_aula = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_aula = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Aula"
        verbose_name_plural = "Aulas"

class ImagemAula(models.Model):
    aula = models.ForeignKey(Aulas, related_name='imagens', on_delete=models.CASCADE)
    imagem = models.ImageField(upload_to='imagens_aulas/')

    def __str__(self):
        return f"Imagem de {self.aula.nome}"
