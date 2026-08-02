"""Adiciona layout de página (cabeçalho) ao relatório."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0005_paragraph_indent_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="report",
            name="page_layout",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Cabeçalho e demais configurações de layout de página.",
                verbose_name="Layout de página",
            ),
        ),
    ]
