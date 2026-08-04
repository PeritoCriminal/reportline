"""
Adiciona linha do diretor pericial na instituição de referência IC-SP.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institution_ic_sp", "0004_forensicteam_address_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="director_display",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Linha exibida no preâmbulo do laudo como Perito Criminal Diretor "
                    "do Instituto de Criminalística."
                ),
                max_length=512,
                verbose_name="Diretor pericial (preâmbulo)",
            ),
        ),
    ]
