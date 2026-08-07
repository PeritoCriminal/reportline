# reportline/institution_ic_sp/forensic_report/services/scene_report_image_nodes.py
"""
Inserção de blocos nativos de imagem e legenda na seção de exame de local.
"""

from __future__ import annotations

from reports.models import ReportBlockType, ReportImage, ReportNode
from reports.services.report_image_upload import build_image_block_content


def insert_scene_report_image_nodes(ctx, report_images: list[dict[str, str]]) -> list[ReportNode]:
    """
    Insere nós IMAGE seguidos de parágrafo legenda após o conteúdo textual da seção.

    ``report_images`` deve conter ``image_id`` e ``caption`` já ajustados pela IA.
    """
    from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
        _insert_scene_report_node,
    )

    created_nodes: list[ReportNode] = []
    for entry in report_images:
        image_id = str(entry.get("image_id", "")).strip()
        caption = str(entry.get("caption", "")).strip()
        if not image_id:
            continue
        try:
            report_image = ReportImage.objects.get(pk=image_id, report=ctx.report)
        except ReportImage.DoesNotExist:
            continue

        image_node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.IMAGE,
            content=build_image_block_content(report_image),
        )
        created_nodes.append(image_node)

        if caption:
            caption_node = _insert_scene_report_node(
                ctx,
                block_type=ReportBlockType.PARAGRAPH,
                content={"text": caption},
                is_caption=True,
            )
            created_nodes.append(caption_node)

    return created_nodes
