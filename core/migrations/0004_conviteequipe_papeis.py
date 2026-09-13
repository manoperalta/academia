"""Convite de equipe pode conceder mais de um papel.

O mesmo CPF pode ser administrador da rede (vale a rede inteira) e gestor de uma
unidade -- o cadastro passa a determinar isso marcando mais de um papel.

Aditiva: ``papeis`` nasce da lista ``papel`` ja existente, sem perder dado.
"""

from django.db import migrations, models


def copiar_papel_para_papeis(apps, schema_editor):
    convite_modelo = apps.get_model("core", "ConviteEquipe")
    for convite in convite_modelo.objects.all().iterator():
        if not convite.papeis:
            convite.papeis = [convite.papel]
            convite.save(update_fields=["papeis"])


def limpar_papeis(apps, schema_editor):
    convite_modelo = apps.get_model("core", "ConviteEquipe")
    convite_modelo.objects.update(papeis=[])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_rede_certificado_emitido_em_rede_certificado_erro_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="conviteequipe",
            name="papeis",
            field=models.JSONField(blank=True, default=list, verbose_name="papéis"),
        ),
        migrations.RunPython(copiar_papel_para_papeis, limpar_papeis),
    ]
