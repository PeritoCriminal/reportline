"""
Montagem de contexto para a tela de edição de relatório.

Organiza nós da árvore em sumário (títulos) e sequência de leitura
do corpo do documento, prontos para renderização nos partials do editor.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from reports.models import Report, ReportBlockType, ReportNode


@dataclass
class ReportOutlineEntry:
    """Entrada do sumário em árvore para blocos do tipo título."""

    node_id: UUID
    label: str
    title_level: int
    depth: int
    children: list[ReportOutlineEntry] = field(default_factory=list)


@dataclass
class ReportBodyEntry:
    """Bloco do corpo do relatório em ordem de leitura."""

    node_id: UUID
    block_type: str
    block_type_label: str
    title_level: int
    content: dict[str, Any]


def build_report_editor_context(report: Report) -> dict[str, Any]:
    """
    Monta estruturas de sumário e corpo a partir dos nós do relatório.

    Retorna dicionário com ``outline_tree`` (somente títulos, hierárquico)
    e ``body_entries`` (todos os blocos em profundidade-primeiro).
    """
    nodes = list(
        report.nodes.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent = _group_nodes_by_parent(nodes)

    return {
        "outline_tree": _build_outline_tree(nodes_by_parent),
        "body_entries": _build_body_entries(nodes_by_parent),
    }


def _group_nodes_by_parent(
    nodes: list[ReportNode],
) -> dict[UUID | None, list[ReportNode]]:
    """Agrupa nós pelo identificador do pai para travessia ordenada."""
    grouped: dict[UUID | None, list[ReportNode]] = defaultdict(list)
    for node in nodes:
        grouped[node.parent_id].append(node)
    for siblings in grouped.values():
        siblings.sort(key=lambda item: (item.position, item.created_at))
    return grouped


def _build_outline_tree(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    parent_id: UUID | None = None,
    depth: int = 0,
) -> list[ReportOutlineEntry]:
    """
    Constrói sumário em árvore incluindo apenas blocos ``heading``.

    Nós intermediários de outros tipos são ignorados no sumário, mas seus
    descendentes títulos permanecem no nível hierárquico correto.
    """
    entries: list[ReportOutlineEntry] = []

    for node in nodes_by_parent.get(parent_id, []):
        block = node.block
        if block.block_type == ReportBlockType.HEADING:
            entries.append(
                ReportOutlineEntry(
                    node_id=node.pk,
                    label=_heading_label(block.content),
                    title_level=block.title_level,
                    depth=depth,
                    children=_build_outline_tree(
                        nodes_by_parent,
                        node.pk,
                        depth + 1,
                    ),
                )
            )
        else:
            entries.extend(
                _build_outline_tree(nodes_by_parent, node.pk, depth)
            )

    return entries


def _build_body_entries(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    parent_id: UUID | None = None,
) -> list[ReportBodyEntry]:
    """Percorre a árvore em profundidade-primeiro produzindo o corpo linear."""
    entries: list[ReportBodyEntry] = []

    for node in nodes_by_parent.get(parent_id, []):
        block = node.block
        entries.append(
            ReportBodyEntry(
                node_id=node.pk,
                block_type=block.block_type,
                block_type_label=block.get_block_type_display(),
                title_level=block.title_level,
                content=block.content or {},
            )
        )
        entries.extend(_build_body_entries(nodes_by_parent, node.pk))

    return entries


def _body_entry_from_node(node: ReportNode) -> ReportBodyEntry:
    """Converte nó persistido em entrada de corpo para templates do editor."""
    block = node.block
    return ReportBodyEntry(
        node_id=node.pk,
        block_type=block.block_type,
        block_type_label=block.get_block_type_display(),
        title_level=block.title_level,
        content=block.content or {},
    )


def render_editable_block_html(
    node: ReportNode,
    request,
    *,
    autofocus: bool = False,
    is_caption: bool = False,
) -> str:
    """Renderiza partial HTML de bloco editável para respostas da API."""
    from django.template.loader import render_to_string

    return render_to_string(
        "reports/includes/report_block_editable.html",
        {
            "entry": _body_entry_from_node(node),
            "autofocus": autofocus,
            "is_caption": is_caption,
        },
        request=request,
    )


def _heading_label(content: dict[str, Any]) -> str:
    """Extrai rótulo de título do payload JSON ou retorna fallback em português."""
    text = content.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return "Título sem texto"
