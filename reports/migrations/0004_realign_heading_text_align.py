"""Corrige alinhamento de títulos conforme numeração (principal centralizado)."""

from django.db import migrations


def realign_heading_text_align(apps, schema_editor):
    """Centraliza somente o título principal; demais títulos ficam à esquerda."""
    ReportModel = apps.get_model("reports", "Report")
    ReportNode = apps.get_model("reports", "ReportNode")

    for report in ReportModel.objects.all():
        nodes = list(
            ReportNode.objects.filter(report=report)
            .select_related("block")
            .order_by("position", "created_at")
        )
        nodes_by_parent: dict = {}
        for node in nodes:
            nodes_by_parent.setdefault(node.parent_id, []).append(node)

        first_heading_skipped = False
        heading_align: dict = {}

        def walk(parent_id=None):
            nonlocal first_heading_skipped
            for node in nodes_by_parent.get(parent_id, []):
                block = node.block
                if block.block_type == "heading":
                    if not first_heading_skipped:
                        heading_align[node.pk] = "center"
                        first_heading_skipped = True
                    else:
                        heading_align[node.pk] = "left"
                walk(node.pk)

        walk()

        for node_id, align in heading_align.items():
            node = ReportNode.objects.select_related("block").get(pk=node_id)
            if node.block.text_align != align:
                node.block.text_align = align
                node.block.save(update_fields=["text_align"])


class Migration(migrations.Migration):

    dependencies = [
        ("reports", "0003_reportblock_text_align"),
    ]

    operations = [
        migrations.RunPython(realign_heading_text_align, migrations.RunPython.noop),
    ]
