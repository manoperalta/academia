from .models import Configuracao, IdentidadeVisual

def site_config(request):
    config = Configuracao.objects.first()
    visual = IdentidadeVisual.objects.first()
    return {
        'site_config': config,
        'site_visual': visual,
    }
