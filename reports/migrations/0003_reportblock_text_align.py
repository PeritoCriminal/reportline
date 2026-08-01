"""Adiciona alinhamento de texto aos blocos de relatório."""

from django.db import migrations, models


def set_default_text_align(apps, schema_editor):
    """Preenche text_align conforme tipo, nível de título e contexto de legenda."""
    ReportBlock = apps.get_model("reports", "ReportBlock")
    ReportNode = apps.get_model("reports", "ReportNode")

    nodes_by_report_parent: dict = {}
    for node in ReportNode.objects.select_related("block").order_by("position", "created_at"):
        key = (node.report_id, node.parent_id)
        nodes_by_report_parent.setdefault(key, []).append(node)

    for block in ReportBlock.objects.all():
        node = ReportNode.objects.filter(block_id=block.pk).first()
        is_caption = False
        if node and block.block_type == "paragraph":
            siblings = nodes_by_report_parent.get((node.report_id, node.parent_id), [])
            try:
                index = siblings.index(node)
            except ValueError:
                index = -1
            if index > 0 and siblings[index - 1].block.block_type == "image":
                is_caption = True

        if block.block_type == "heading":
            align = "center" if block.title_level == 0 else "left"
        elif block.block_type == "paragraph":
            align = "center" if is_caption else "justify"
        elif block.block_type in ("ordered_list", "unordered_list"):
            align = "left"
        elif block.block_type == "image":
            align = "center"
        elif block.block_type == "link":
            align = "justify"
        else:
            align = "left"

        block.text_align = align
        block.save(update_fields=["text_align"])


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0002_report_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportblock",
            name="text_align",
            field=models.CharField(
                choices=[
                    ("left", "Esquerda"),
                    ("center", "Centro"),
                    ("right", "Direita"),
                    ("justify", "Justificado"),
                ],
                default="justify",
                max_length=10,
                verbose_name="Alinhamento do texto",
            ),
        ),
        migrations.RunPython(set_default_text_align, migrations.RunPython.noop),
    ]
