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

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
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
    old_content = block.content

    block.block_type = target_type
    block.content = normalize_block_content(target_type, content)
    if title_level is not None:
        block.title_level = title_level
    block.save(update_fields=["block_type", "content", "title_level", "updated_at"])

    from reports.services.report_block_image_cleanup import delete_removed_block_images

    delete_removed_block_images(target_type, old_content, block.content)
    return node


def _fractional_position_before(
    report: Report,
    parent_id: UUID | None,
    before_node: ReportNode,
) -> Decimal:
    """Calcula posição decimal entre o irmão anterior e o nó de referência."""
    previous_sibling = (
        ReportNode.objects.filter(
            report=report,
            parent_id=parent_id,
            position__lt=before_node.position,
        )
        .order_by("-position")
        .first()
    )
    if previous_sibling:
        return (previous_sibling.position + before_node.position) / 2
    return before_node.position / 2 if before_node.position else Decimal("0.5")


@transaction.atomic
def insert_sibling_before(
    report: Report,
    before_node: ReportNode,
    *,
    block_type: str,
    content: dict[str, Any] | None = None,
    title_level: int | None = None,
) -> ReportNode:
    """Insere nó irmão imediatamente antes de ``before_node`` na mesma profundidade."""
    if before_node.report_id != report.pk:
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
    position = _fractional_position_before(report, before_node.parent_id, before_node)
    return ReportNode.objects.create(
        report=report,
        parent=before_node.parent,
        block=block,
        position=position,
    )


@transaction.atomic
def delete_node(node: ReportNode) -> None:
    """
    Remove nó e bloco associado.

    Impede exclusão do único nó restante do relatório para evitar documento vazio.
    """
    if node.report.nodes.count() <= 1:
        raise ValidationError("Não é possível excluir o único bloco do relatório.")
    node.delete()


@transaction.atomic
def update_list_items(node: ReportNode, *, items: list[str]) -> ReportNode:
    """Persiste itens completos de uma lista no mesmo nó."""
    block = node.block
    block.content = normalize_block_content(block.block_type, {"items": items})
    block.save(update_fields=["content", "updated_at"])
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
def reorder_heading_siblings(
    report: Report,
    parent_id: UUID | None,
    ordered_heading_ids: list[UUID],
) -> None:
    """
    Reordena títulos irmãos preservando blocos não-título entre eles.

    Recebe a nova ordem dos nós ``heading`` sob ``parent_id`` e reatribui
    posições decimais sequenciais à lista completa de irmãos.
    """
    siblings = list(
        ReportNode.objects.filter(report=report, parent_id=parent_id)
        .select_related("block")
        .order_by("position", "created_at")
    )
    if not siblings:
        if ordered_heading_ids:
            raise ValidationError("Nenhum nó irmão encontrado para o pai informado.")
        return

    headings = [
        node
        for node in siblings
        if node.block.block_type == ReportBlockType.HEADING
    ]
    heading_ids = {node.pk for node in headings}
    if set(ordered_heading_ids) != heading_ids:
        raise ValidationError("A lista de títulos não corresponde aos irmãos do pai informado.")
    if len(ordered_heading_ids) < 2:
        raise ValidationError("São necessários ao menos dois títulos para reordenar.")

    heading_by_id = {node.pk: node for node in headings}
    for node_id in ordered_heading_ids:
        node = heading_by_id[node_id]
        if node.parent_id != parent_id:
            raise ValidationError(
                "Não é permitido mover títulos para fora do grupo pai informado."
            )

    new_headings = [heading_by_id[node_id] for node_id in ordered_heading_ids]

    heading_indices = [
        index
        for index, node in enumerate(siblings)
        if node.block.block_type == ReportBlockType.HEADING
    ]
    new_order = list(siblings)
    for slot, sibling_index in enumerate(heading_indices):
        new_order[sibling_index] = new_headings[slot]

    for index, node in enumerate(new_order, start=1):
        new_position = Decimal(index)
        if node.position != new_position:
            node.position = new_position
            node.save(update_fields=["position"])


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
