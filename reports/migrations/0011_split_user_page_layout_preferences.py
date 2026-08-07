# reportline/reports/migrations/0011_split_user_page_layout_preferences.py
"""
Separa preferências de layout pessoal e institucional por usuário.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0010_alter_reportblock_line_spacing"),
    ]

    operations = [
        migrations.RenameField(
            model_name="reportuserconfig",
            old_name="page_layout",
            new_name="personal_page_layout",
        ),
        migrations.AlterField(
            model_name="reportuserconfig",
            name="personal_page_layout",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Último cabeçalho e rodapé de relatórios comuns editados pelo usuário, "
                    "aplicados a novos relatórios pessoais."
                ),
                verbose_name="Layout de página pessoal",
            ),
        ),
        migrations.AddField(
            model_name="reportuserconfig",
            name="institutional_page_layout",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Último cabeçalho e rodapé de laudos periciais editados pelo usuário, "
                    "aplicados a novos laudos institucionais."
                ),
                verbose_name="Layout de página institucional",
            ),
        ),
    ]
