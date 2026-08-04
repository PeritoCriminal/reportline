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
from reports.services.report_inline_text import inline_text_plain
from reports.services.report_page_layout import enrich_page_layout_for_editor
from reports.services.report_caption_numbering import build_caption_number_map
from reports.services.report_heading_numbering import (
    build_heading_number_map,
    build_heading_number_map_for_report,
)
from reports.services.report_user_config import serialize_report_config


@dataclass
class ReportOutlineEntry:
    """Entrada do sumário em árvore para blocos do tipo título."""

    node_id: UUID
    label: str
    title_level: int
    depth: int
    report_parent_id: UUID | None
    number: str = ""
    children: list[ReportOutlineEntry] = field(default_factory=list)


@dataclass
class ReportBodyEntry:
    """Bloco do corpo do relatório em ordem de leitura."""

    node_id: UUID
    block_type: str
    block_type_label: str
    title_level: int
    content: dict[str, Any]
    heading_number: str = ""
    is_main_title: bool = False
    is_caption: bool = False
    caption_number: int = 0
    text_align: str = "justify"
    indent_level: int = 0
    first_line_indent: bool = True
    line_spacing: str = "normal"


def _enrich_block_content(block_type: str, content: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta campos derivados ao payload do bloco para templates."""
    enriched = dict(content)
    if block_type == ReportBlockType.IMAGE and enriched.get("file"):
        from django.core.files.storage import default_storage

        enriched["url"] = default_storage.url(enriched["file"])
    if block_type == ReportBlockType.TABLE:
        from reports.services.report_table_cell_content import enrich_table_body_cell, enrich_table_header_cell
        from reports.services.report_table_column_widths import normalize_column_widths

        headers = enriched.get("headers", [])
        enriched["headers"] = [enrich_table_header_cell(header) for header in headers]
        enriched["rows"] = [
            [enrich_table_body_cell(cell) for cell in row]
            for row in enriched.get("rows", [])
        ]
        enriched["column_widths"] = normalize_column_widths(
            enriched.get("column_widths"),
            len(headers),
        )
    return enriched


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
    heading_numbers = build_heading_number_map_for_report(report)
    caption_numbers = build_caption_number_map(
        nodes_by_parent,
        number_captions=report.number_captions,
    )
    main_title_id = _main_title_node_id(nodes_by_parent)

    return {
        "outline_tree": _build_outline_tree(
            nodes_by_parent,
            heading_numbers=heading_numbers,
        ),
        "body_entries": _build_body_entries(
            nodes_by_parent,
            heading_numbers=heading_numbers,
            caption_numbers=caption_numbers,
            main_title_id=main_title_id,
        ),
        "heading_numbers": heading_numbers,
        "caption_numbers": caption_numbers,
        "report_config": serialize_report_config(report),
        "page_layout": enrich_page_layout_for_editor(report.page_layout),
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


def _collect_headings_in_reading_order(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    parent_id: UUID | None = None,
) -> list[ReportNode]:
    """Coleta títulos em ordem de leitura (profundidade-primeiro)."""
    headings: list[ReportNode] = []
    for node in nodes_by_parent.get(parent_id, []):
        block = node.block
        if block.block_type == ReportBlockType.HEADING:
            headings.append(node)
        headings.extend(
            _collect_headings_in_reading_order(nodes_by_parent, node.pk)
        )
    return headings


def _build_outline_tree(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    *,
    heading_numbers: dict[UUID, str],
) -> list[ReportOutlineEntry]:
    """
    Constrói sumário hierárquico a partir de ``title_level`` em ordem de leitura.

    A profundidade visual segue os níveis de título (como a numeração automática),
    independentemente da árvore de nós ``ReportNode.parent``.
    """
    headings = _collect_headings_in_reading_order(nodes_by_parent)
    return _build_outline_tree_from_title_levels(headings, heading_numbers)


def _build_outline_tree_from_title_levels(
    headings: list[ReportNode],
    heading_numbers: dict[UUID, str],
) -> list[ReportOutlineEntry]:
    """Empilha títulos consecutivos conforme ``title_level`` decrescente na pilha."""
    root: list[ReportOutlineEntry] = []
    stack: list[ReportOutlineEntry] = []

    for node in headings:
        block = node.block
        entry = ReportOutlineEntry(
            node_id=node.pk,
            label=_heading_label(block.content),
            title_level=block.title_level,
            depth=0,
            report_parent_id=node.parent_id,
            number=heading_numbers.get(node.pk, ""),
        )
        while stack and stack[-1].title_level >= entry.title_level:
            stack.pop()
        if stack:
            parent_entry = stack[-1]
            entry.depth = parent_entry.depth + 1
            parent_entry.children.append(entry)
        else:
            entry.depth = 0
            root.append(entry)
        stack.append(entry)

    return root


def _is_caption_paragraph(
    node: ReportNode,
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
) -> bool:
    """Indica parágrafo imediatamente após bloco de imagem (legenda)."""
    if node.block.block_type != ReportBlockType.PARAGRAPH:
        return False

    siblings = nodes_by_parent.get(node.parent_id, [])
    try:
        index = siblings.index(node)
    except ValueError:
        return False

    if index == 0:
        return False

    return siblings[index - 1].block.block_type == ReportBlockType.IMAGE


def is_caption_paragraph_node(node: ReportNode) -> bool:
    """Indica se o nó é parágrafo legenda imediatamente após imagem."""
    nodes = list(
        node.report.nodes.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent = _group_nodes_by_parent(nodes)
    return _is_caption_paragraph(node, nodes_by_parent)


def _main_title_node_id(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
) -> UUID | None:
    """Retorna o nó do título principal (primeiro título em ordem de leitura)."""
    headings = _collect_headings_in_reading_order(nodes_by_parent)
    return headings[0].pk if headings else None


def _build_body_entries(
    nodes_by_parent: dict[UUID | None, list[ReportNode]],
    parent_id: UUID | None = None,
    *,
    heading_numbers: dict[UUID, str],
    caption_numbers: dict[UUID, int] | None = None,
    main_title_id: UUID | None = None,
) -> list[ReportBodyEntry]:
    """Percorre a árvore em profundidade-primeiro produzindo o corpo linear."""
    numbers = caption_numbers or {}
    entries: list[ReportBodyEntry] = []

    for node in nodes_by_parent.get(parent_id, []):
        block = node.block
        is_caption = _is_caption_paragraph(node, nodes_by_parent)
        entries.append(
            ReportBodyEntry(
                node_id=node.pk,
                block_type=block.block_type,
                block_type_label=block.get_block_type_display(),
                title_level=block.title_level,
                content=_enrich_block_content(block.block_type, block.content or {}),
                heading_number=heading_numbers.get(node.pk, ""),
                is_main_title=node.pk == main_title_id,
                is_caption=is_caption,
                caption_number=numbers.get(node.pk, 0) if is_caption else 0,
                text_align=block.text_align,
                indent_level=block.indent_level,
                first_line_indent=block.first_line_indent,
                line_spacing=block.line_spacing,
            )
        )
        entries.extend(
            _build_body_entries(
                nodes_by_parent,
                node.pk,
                heading_numbers=heading_numbers,
                caption_numbers=numbers,
                main_title_id=main_title_id,
            )
        )

    return entries


def _body_entry_from_node(
    node: ReportNode,
    *,
    heading_numbers: dict[UUID, str] | None = None,
    caption_numbers: dict[UUID, int] | None = None,
) -> ReportBodyEntry:
    """Converte nó persistido em entrada de corpo para templates do editor."""
    block = node.block
    numbers = heading_numbers
    if numbers is None:
        numbers = build_heading_number_map_for_node(node)

    caption_map = caption_numbers
    if caption_map is None:
        nodes = list(
            node.report.nodes.select_related("block").order_by("position", "created_at")
        )
        nodes_by_parent = _group_nodes_by_parent(nodes)
        caption_map = build_caption_number_map(
            nodes_by_parent,
            number_captions=node.report.number_captions,
        )

    nodes = list(
        node.report.nodes.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent = _group_nodes_by_parent(nodes)
    is_caption = _is_caption_paragraph(node, nodes_by_parent)
    main_title_id = _main_title_node_id(nodes_by_parent)

    return ReportBodyEntry(
        node_id=node.pk,
        block_type=block.block_type,
        block_type_label=block.get_block_type_display(),
        title_level=block.title_level,
        content=_enrich_block_content(block.block_type, block.content or {}),
        heading_number=numbers.get(node.pk, ""),
        is_main_title=node.pk == main_title_id,
        is_caption=is_caption,
        caption_number=caption_map.get(node.pk, 0) if is_caption else 0,
        text_align=block.text_align,
        indent_level=block.indent_level,
        first_line_indent=block.first_line_indent,
        line_spacing=block.line_spacing,
    )


def build_heading_number_map_for_node(node: ReportNode) -> dict[UUID, str]:
    """Recalcula numeração de títulos a partir do relatório do nó informado."""
    return build_heading_number_map_for_report(node.report)


def render_outline_tree_html(report: Report, request) -> str:
    """Renderiza partial HTML do sumário lateral para atualização assíncrona."""
    from django.template.loader import render_to_string

    context = build_report_editor_context(report)
    return render_to_string(
        "reports/includes/report_outline_tree.html",
        context,
        request=request,
    )


def list_body_node_ids(report: Report) -> list[str]:
    """Lista IDs dos nós do corpo em ordem de leitura (profundidade-primeiro)."""
    nodes = list(report.nodes.order_by("position", "created_at"))
    nodes_by_parent = _group_nodes_by_parent(nodes)

    def collect(parent_id: UUID | None = None) -> list[str]:
        ordered: list[str] = []
        for node in nodes_by_parent.get(parent_id, []):
            ordered.append(str(node.pk))
            ordered.extend(collect(node.pk))
        return ordered

    return collect(None)


def render_outline_refresh_payload(report: Report, request) -> dict[str, str | dict[str, str]]:
    """Monta HTML do sumário e mapa de numeração para atualização assíncrona."""
    context = build_report_editor_context(report)
    from django.template.loader import render_to_string

    html = render_to_string(
        "reports/includes/report_outline_tree.html",
        context,
        request=request,
    )
    heading_numbers = {
        str(node_id): number
        for node_id, number in context["heading_numbers"].items()
    }
    return {"html": html, "heading_numbers": heading_numbers}


def render_page_header_html(page_layout: dict[str, Any], request) -> str:
    """Renderiza partial HTML do cabeçalho de página para o editor."""
    from django.template.loader import render_to_string

    enriched = enrich_page_layout_for_editor(page_layout)
    return render_to_string(
        "reports/includes/report_page_header_editable.html",
        {"page_layout": enriched},
        request=request,
    )


def render_page_footer_html(page_layout: dict[str, Any], request) -> str:
    """Renderiza partial HTML do rodapé de página para o editor."""
    from django.template.loader import render_to_string

    enriched = enrich_page_layout_for_editor(page_layout)
    return render_to_string(
        "reports/includes/report_page_footer_editable.html",
        {"page_layout": enriched},
        request=request,
    )


def render_editable_block_html(
    node: ReportNode,
    request,
    *,
    autofocus: bool = False,
    is_caption: bool | None = None,
    focus_table_part: str | None = None,
    focus_table_row: int | None = None,
    focus_table_col: int | None = None,
) -> str:
    """Renderiza partial HTML de bloco editável para respostas da API."""
    from django.template.loader import render_to_string

    entry = _body_entry_from_node(node)
    if is_caption is None and node.block.block_type == ReportBlockType.PARAGRAPH:
        nodes = list(
            node.report.nodes.select_related("block").order_by("position", "created_at")
        )
        nodes_by_parent = _group_nodes_by_parent(nodes)
        entry.is_caption = _is_caption_paragraph(node, nodes_by_parent)
    elif is_caption is not None:
        entry.is_caption = is_caption

    return render_to_string(
        "reports/includes/report_block_editable.html",
        {
            "entry": entry,
            "autofocus": autofocus,
            "is_caption": entry.is_caption,
            "focus_table_part": focus_table_part,
            "focus_table_row": focus_table_row,
            "focus_table_col": focus_table_col,
        },
        request=request,
    )


def _heading_label(content: dict[str, Any]) -> str:
    """Extrai rótulo de título do payload JSON ou retorna fallback em português."""
    text = content.get("text")
    if isinstance(text, str) and text.strip():
        plain = inline_text_plain(text).strip()
        if plain:
            return plain
    return "Título sem texto"
