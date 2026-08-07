# reportline/reports/migrations/0005_paragraph_indent_level.py
"""Substitui indent_paragraph por indent_level e padroniza recuo de 1ª linha."""

from django.core.validators import MaxValueValidator
from django.db import migrations, models


def migrate_paragraph_indent(apps, schema_editor):
    """Converte recuo booleano em nível e aplica 1ª linha em parágrafos de corpo."""
    ReportBlock = apps.get_model("reports", "ReportBlock")
    ReportNode = apps.get_model("reports", "ReportNode")

    for block in ReportBlock.objects.filter(indent_paragraph=True):
        block.indent_level = 1
        block.save(update_fields=["indent_level"])

    nodes = list(
        ReportNode.objects.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent: dict = {}
    for node in nodes:
        nodes_by_parent.setdefault(node.parent_id, []).append(node)

    caption_node_ids: set = set()

    for siblings in nodes_by_parent.values():
        for index, node in enumerate(siblings):
            block = node.block
            if block.block_type != "paragraph":
                continue
            if index == 0:
                continue
            previous = siblings[index - 1].block
            if previous.block_type == "image":
                caption_node_ids.add(node.pk)

    for node in nodes:
        block = node.block
        if block.block_type != "paragraph":
            continue
        if node.pk in caption_node_ids:
            block.first_line_indent = False
        else:
            block.first_line_indent = True
        block.save(update_fields=["first_line_indent"])


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0004_realign_heading_text_align"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportblock",
            name="indent_level",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Recuo progressivo do bloco (0 = sem recuo; máximo 5).",
                validators=[MaxValueValidator(5)],
                verbose_name="Nível de recuo",
            ),
        ),
        migrations.RunPython(migrate_paragraph_indent, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="reportblock",
            name="indent_paragraph",
        ),
        migrations.AlterField(
            model_name="reportblock",
            name="first_line_indent",
            field=models.BooleanField(
                default=True,
                verbose_name="Recuar primeira linha",
            ),
        ),
    ]
