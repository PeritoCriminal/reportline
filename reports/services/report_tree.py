"""
Operações de árvore de nós de relatório.

Centraliza inserção de irmãos, atualização de blocos e extensão
de listas para o editor interativo.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from reports.models import Report, ReportBlock, ReportNode
from reports.services.report_block_content import (
    default_content_for_block_type,
    normalize_block_content,
)
from reports.services.report_block_sequence import default_title_level_for_block_type


def _fractional_position_after(
    report: Report,
    parent_id: UUID | None,
    after_node: ReportNode,
) -> Decimal:
    """Calcula posição decimal entre o nó atual e o próximo irmão."""
    next_sibling = (
        ReportNode.objects.filter(
            report=report,
            parent_id=parent_id,
            position__gt=after_node.position,
        )
        .order_by("position")
        .first()
    )
    if next_sibling:
        return (after_node.position + next_sibling.position) / 2
    return after_node.position + Decimal("1")


@transaction.atomic
def update_node_block(
    node: ReportNode,
    *,
    content: dict[str, Any],
    block_type: str | None = None,
    title_level: int | None = None,
) -> ReportNode:
    """Atualiza conteúdo e metadados opcionais do bloco associado ao nó."""
    block = node.block
    target_type = block_type or block.block_type
    block.block_type = target_type
    block.content = normalize_block_content(target_type, content)
    if title_level is not None:
        block.title_level = title_level
    block.save(update_fields=["block_type", "content", "title_level", "updated_at"])
    return node


@transaction.atomic
def insert_sibling_after(
    report: Report,
    after_node: ReportNode,
    *,
    block_type: str,
    content: dict[str, Any] | None = None,
    title_level: int | None = None,
) -> ReportNode:
    """
    Insere nó irmão imediatamente após ``after_node`` na mesma profundidade.
    """
    if after_node.report_id != report.pk:
        raise ValidationError("Nó não pertence ao relatório informado.")

    payload = content if content is not None else default_content_for_block_type(block_type)
    normalized = normalize_block_content(block_type, payload)
    level = (
        title_level
        if title_level is not None
        else default_title_level_for_block_type(block_type)
    )

    block = ReportBlock.objects.create(
        block_type=block_type,
        content=normalized,
        title_level=level,
    )
    position = _fractional_position_after(report, after_node.parent_id, after_node)
    return ReportNode.objects.create(
        report=report,
        parent=after_node.parent,
        block=block,
        position=position,
    )


@transaction.atomic
def append_list_item(node: ReportNode, *, items: list[str]) -> tuple[ReportNode, int]:
    """
    Persiste itens da lista e acrescenta entrada vazia para novo foco.

    Retorna o nó atualizado e o índice do novo item vazio.
    """
    block = node.block
    normalized = normalize_block_content(block.block_type, {"items": items + [""]})
    block.content = normalized
    block.save(update_fields=["content", "updated_at"])
    return node, len(normalized["items"]) - 1
