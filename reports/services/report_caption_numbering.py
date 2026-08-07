# reportline/reports/services/report_caption_numbering.py
"""
Numeração automática de legendas de imagens em laudos.

Atribui sequência ``Figura N`` apenas a parágrafos-legenda com texto,
em ordem de leitura profundidade-primeiro, ignorando legendas vazias.
"""

from __future__ import annotations

from uuid import UUID

from reports.models import ReportBlockType, ReportNode
from reports.services.report_inline_text import inline_text_plain


def build_caption_number_map(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    *,
    number_captions: bool,
    parent_id: UUID | None = None,
) -> dict[UUID, int]:
    """
    Percorre a árvore em profundidade-primeiro e produz mapa nó da legenda → número.

    Considera somente blocos de imagem seguidos de parágrafo-legenda imediato
    com texto visível após sanitização inline, na ordem de leitura do documento.
    """
    if not number_captions:
        return {}

    numbers: dict[UUID, int] = {}
    counter = 0

    def walk(current_parent_id: UUID | None) -> None:
        nonlocal counter
        for node in nodes_by_parent.get(current_parent_id, []):
            block = node.block
            if block.block_type == ReportBlockType.IMAGE:
                caption_node = _caption_node_after_image(node, nodes_by_parent)
                if caption_node and _caption_has_text(caption_node):
                    counter += 1
                    numbers[caption_node.pk] = counter
            walk(node.pk)

    walk(parent_id)
    return numbers


def _caption_node_after_image(
    image_node: ReportNode,
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
) -> ReportNode | None:
    """Retorna parágrafo-legenda imediatamente após bloco de imagem, se existir."""
    siblings = nodes_by_parent.get(image_node.parent_id, [])
    try:
        index = siblings.index(image_node)
    except ValueError:
        return None

    if index + 1 >= len(siblings):
        return None

    next_node = siblings[index + 1]
    if next_node.block.block_type != ReportBlockType.PARAGRAPH:
        return None

    return next_node


def _caption_has_text(caption_node: ReportNode) -> bool:
    """Indica se a legenda possui texto visível."""
    content = caption_node.block.content or {}
    text = content.get("text", "")
    if not isinstance(text, str):
        return False
    return bool(inline_text_plain(text).strip())
