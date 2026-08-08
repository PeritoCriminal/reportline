# reportline/reports/services/report_image_nodes.py
"""
Inserção de blocos nativos IMAGE e parágrafo legenda após um ponto de ancoragem.
"""

from __future__ import annotations

from typing import Callable, Protocol

from reports.models import ReportBlockType, ReportImage, ReportNode
from reports.services.report_caption_text import normalize_caption_text
from reports.services.report_image_upload import build_image_block_content

EMPTY_IMAGE_CAPTION_PLACEHOLDER = "—"


class ReportNodeInserter(Protocol):
    """Protocolo para inserção de nó irmão após âncora mutável."""

    def __call__(
        self,
        ctx,
        *,
        block_type: str,
        content: dict,
        title_level: int = 0,
        text_align: str | None = None,
        first_line_indent: bool | None = None,
        is_caption: bool = False,
    ) -> ReportNode: ...


def insert_report_image_nodes(
    ctx,
    report_images: list[dict[str, str]],
    *,
    insert_node: ReportNodeInserter,
) -> list[ReportNode]:
    """
    Insere nós IMAGE seguidos de parágrafo legenda.

    ``report_images`` deve conter ``image_id`` e ``caption`` já ajustados.
    """
    created_nodes: list[ReportNode] = []
    for entry in report_images:
        image_id = str(entry.get("image_id", "")).strip()
        caption = normalize_caption_text(str(entry.get("caption", "")).strip())
        if not caption:
            caption = EMPTY_IMAGE_CAPTION_PLACEHOLDER
        if not image_id:
            continue
        try:
            report_image = ReportImage.objects.get(pk=image_id, report=ctx.report)
        except ReportImage.DoesNotExist:
            continue

        image_node = insert_node(
            ctx,
            block_type=ReportBlockType.IMAGE,
            content=build_image_block_content(report_image),
        )
        created_nodes.append(image_node)

        caption_node = insert_node(
            ctx,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": caption},
            is_caption=True,
        )
        created_nodes.append(caption_node)

    return created_nodes
