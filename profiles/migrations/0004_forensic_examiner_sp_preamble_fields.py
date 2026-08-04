"""
Adiciona tratamento gramatical e linha do diretor no perfil pericial SP.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0003_forensic_examiner_sp_nucleus_assignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="forensicexaminersp",
            name="calling_gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "Masculino"), ("female", "Feminino")],
                help_text="Define concordância de gênero no preâmbulo e na designação pericial.",
                max_length=10,
                verbose_name="Tratamento gramatical",
            ),
        ),
        migrations.AddField(
            model_name="forensicexaminersp",
            name="director_display",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Linha do Perito Criminal Diretor impressa no preâmbulo; "
                    "padrão copiado da instituição quando não informado."
                ),
                max_length=512,
                verbose_name="Diretor pericial (preâmbulo)",
            ),
        ),
    ]
