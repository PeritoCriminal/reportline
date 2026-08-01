"""
Numeração hierárquica automática de títulos em relatórios.

Atribui sequências como 1, 1.1 e 1.1.1 conforme ``title_level`` dos blocos
heading em ordem de leitura profundidade-primeiro na árvore de nós.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from reports.models import ReportBlockType, ReportNode

MAX_HEADING_LEVEL = 3


def build_heading_number_map(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    parent_id: UUID | None = None,
    counters: list[int] | None = None,
    *,
    first_heading_skipped: bool | None = None,
) -> dict[UUID, str]:
    """
    Percorre a árvore em profundidade-primeiro e produz mapa nó → numeração.

    O **primeiro título** do relatório (título principal, nível 1) fica sem
    numeração; os demais seguem a hierarquia ``1``, ``1.1``, ``1.2``, ``2``…

    Níveis intermediários zerados recebem ``1`` implícito ao saltar profundidade.
    """
    if counters is None:
        counters = [0] * (MAX_HEADING_LEVEL + 1)
    if first_heading_skipped is None:
        first_heading_skipped = False

    numbers: dict[UUID, str] = {}

    for node in nodes_by_parent.get(parent_id, []):
        block = node.block
        if block.block_type == ReportBlockType.HEADING:
            if not first_heading_skipped:
                numbers[node.pk] = ""
                first_heading_skipped = True
            else:
                level = _clamp_heading_level(block.title_level)
                counters[level] += 1
                for index in range(level):
                    if counters[index] == 0:
                        counters[index] = 1
                for index in range(level + 1, len(counters)):
                    counters[index] = 0
                numbers[node.pk] = ".".join(
                    str(counters[index]) for index in range(level + 1)
                )

        numbers.update(
            build_heading_number_map(
                nodes_by_parent,
                node.pk,
                counters,
                first_heading_skipped=first_heading_skipped,
            )
        )

    return numbers


def group_nodes_by_parent(nodes: list[ReportNode]) -> dict[UUID | None, list[ReportNode]]:
    """Agrupa nós pelo pai para travessia ordenada."""
    grouped: dict[UUID | None, list[ReportNode]] = defaultdict(list)
    for node in nodes:
        grouped[node.parent_id].append(node)
    for siblings in grouped.values():
        siblings.sort(key=lambda item: (item.position, item.created_at))
    return grouped


def build_heading_number_map_for_report(report) -> dict[UUID, str]:
    """Monta numeração de títulos a partir dos nós persistidos do relatório."""
    nodes = list(
        report.nodes.select_related("block").order_by("position", "created_at")
    )
    return build_heading_number_map(group_nodes_by_parent(nodes))


def _clamp_heading_level(level: int) -> int:
    """Restringe nível de título ao intervalo suportado pelo editor."""
    return min(max(level, 0), MAX_HEADING_LEVEL)
