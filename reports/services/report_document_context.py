"""
Montagem de contexto para renderização de leitura do relatório.

Transforma a sequência de blocos do editor em seções prontas para
templates de documento (preview e PDF), com HTML sanitizado e URLs absolutas.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from django.contrib.staticfiles import finders
from django.http import HttpRequest

from reports.models import Report, ReportBlockType
from reports.services.report_editor_context import (
    ReportBodyEntry,
    build_report_editor_context,
)
from reports.services.report_inline_text import (
    sanitize_header_text_html,
    sanitize_inline_text_html,
)
from reports.services.report_page_layout import (
    enrich_page_layout_for_editor,
    prepare_logo_cell_for_document,
)


@dataclass
class ReportDocumentSection:
    """Bloco do documento em ordem de leitura para templates de leitura."""

    node_id: UUID
    block_type: str
    body_html: str = ""
    heading_number: str = ""
    caption_number: int = 0
    is_caption: bool = False
    is_main_title: bool = False
    title_level: int = 0
    text_align: str = "justify"
    indent_level: int = 0
    first_line_indent: bool = True
    line_spacing: str = "normal"
    content: dict[str, Any] = field(default_factory=dict)
    list_items_html: list[str] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)


def build_report_document_context(report: Report, request: HttpRequest) -> dict[str, Any]:
    """
    Monta contexto de leitura a partir do relatório persistido.

    Reutiliza ``build_report_editor_context`` para ordem e enriquecimento
    dos blocos, produzindo ``sections`` com HTML sanitizado e metadados
    de numeração para renderização fora do editor.
    """
    editor_context = build_report_editor_context(report)
    sections = [
        _section_from_body_entry(entry, request)
        for entry in editor_context["body_entries"]
    ]
    return {
        "report": report,
        "sections": sections,
        "report_config": editor_context["report_config"],
        "heading_numbers": editor_context["heading_numbers"],
        "caption_numbers": editor_context["caption_numbers"],
        "page_layout": _prepare_page_layout_for_document(
            editor_context["page_layout"],
            request,
        ),
        "document_styles": load_report_document_styles(),
        "document_script": load_report_document_script(),
    }


def load_report_document_script() -> str:
    """
    Carrega script de paginação do preview para embutir inline no HTML.

    Mantém o documento autônomo (sem dependência de cache de estático externo).
    """
    script_path = finders.find("reports/js/report_document_pagination.js")
    if not script_path:
        raise FileNotFoundError("Arquivo reports/js/report_document_pagination.js não encontrado.")
    return Path(script_path).read_text(encoding="utf-8")


def load_report_document_styles() -> str:
    """
    Carrega CSS de leitura do laudo para embutir inline no HTML do documento.

    Usa finders de arquivos estáticos para funcionar em desenvolvimento e após
    ``collectstatic``; evita link externo que poderia ficar stale no Chromium.
    """
    css_path = finders.find("reports/css/report_document.css")
    if not css_path:
        raise FileNotFoundError("Arquivo reports/css/report_document.css não encontrado.")
    return Path(css_path).read_text(encoding="utf-8")


def _section_from_body_entry(
    entry: ReportBodyEntry,
    request: HttpRequest,
) -> ReportDocumentSection:
    """Converte entrada do corpo do editor em seção de documento de leitura."""
    content = _content_for_document_reading(entry.block_type, entry.content, request)
    body_html = _body_html_for_block(entry.block_type, entry.content)
    list_items_html = _list_items_html(entry.block_type, entry.content)
    figures = _figures_for_block(entry.block_type, content, request)

    return ReportDocumentSection(
        node_id=entry.node_id,
        block_type=entry.block_type,
        body_html=body_html,
        heading_number=entry.heading_number,
        caption_number=entry.caption_number,
        is_caption=entry.is_caption,
        is_main_title=entry.is_main_title,
        title_level=entry.title_level,
        text_align=entry.text_align,
        indent_level=entry.indent_level,
        first_line_indent=entry.first_line_indent,
        line_spacing=entry.line_spacing,
        content=content,
        list_items_html=list_items_html,
        figures=figures,
    )


def _body_html_for_block(block_type: str, content: dict[str, Any]) -> str:
    """Extrai e sanitiza HTML inline do campo textual principal do bloco."""
    if block_type in {
        ReportBlockType.HEADING,
        ReportBlockType.PARAGRAPH,
        ReportBlockType.LINK,
    }:
        return sanitize_inline_text_html(str(content.get("text", "")))
    return ""


def _list_items_html(block_type: str, content: dict[str, Any]) -> list[str]:
    """Sanitiza itens de lista numerada ou com marcadores."""
    if block_type not in {ReportBlockType.ORDERED_LIST, ReportBlockType.UNORDERED_LIST}:
        return []

    items = content.get("items", [])
    if not isinstance(items, list):
        return []

    return [sanitize_inline_text_html(str(item)) for item in items]


def _figures_for_block(
    block_type: str,
    content: dict[str, Any],
    request: HttpRequest,
) -> list[dict[str, Any]]:
    """Monta metadados de figura com URL absoluta para blocos de imagem."""
    if block_type != ReportBlockType.IMAGE:
        return []

    url = content.get("url", "")
    if not url:
        return []

    return [
        {
            "url": _absolute_url(request, url),
            "alt": str(content.get("alt", "")),
            "width": content.get("width", 0),
            "height": content.get("height", 0),
        }
    ]


def _content_for_document_reading(
    block_type: str,
    content: dict[str, Any],
    request: HttpRequest,
) -> dict[str, Any]:
    """Prepara payload do bloco com URLs absolutas para renderização de leitura."""
    prepared = deepcopy(content)

    if block_type == ReportBlockType.IMAGE and prepared.get("url"):
        prepared["url"] = _absolute_url(request, prepared["url"])

    if block_type == ReportBlockType.TABLE:
        prepared["headers"] = [
            _prepare_table_header_cell(header) for header in prepared.get("headers", [])
        ]
        prepared["rows"] = [
            [_prepare_table_body_cell(cell, request) for cell in row]
            for row in prepared.get("rows", [])
        ]

    return prepared


def _prepare_table_header_cell(cell: Any) -> dict[str, Any]:
    """Sanitiza texto de cabeçalho de tabela para leitura."""
    if isinstance(cell, str):
        return {"text": sanitize_inline_text_html(cell), "align": "left"}

    if isinstance(cell, dict):
        return {
            **cell,
            "text": sanitize_inline_text_html(str(cell.get("text", ""))),
        }

    return {"text": "", "align": "left"}


def _prepare_table_body_cell(cell: Any, request: HttpRequest) -> Any:
    """Sanitiza célula de corpo de tabela e resolve URL absoluta de imagens."""
    if isinstance(cell, str):
        return {
            "type": "text",
            "text": sanitize_inline_text_html(cell),
            "align": "left",
        }

    if not isinstance(cell, dict):
        return cell

    if cell.get("type") == "image":
        prepared = dict(cell)
        if prepared.get("url"):
            prepared["url"] = _absolute_url(request, prepared["url"])
        return prepared

    prepared = dict(cell)
    if prepared.get("type", "text") == "text":
        prepared["text"] = sanitize_inline_text_html(str(prepared.get("text", "")))
    return prepared


def _absolute_url(request: HttpRequest, url: str) -> str:
    """Converte URL relativa de mídia em endereço absoluto acessível externamente."""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return request.build_absolute_uri(url)


def _prepare_page_layout_for_document(
    page_layout: dict[str, Any],
    request: HttpRequest,
) -> dict[str, Any]:
    """Prepara cabeçalho/rodapé com URLs absolutas e texto sanitizado para leitura."""
    prepared = deepcopy(enrich_page_layout_for_editor(page_layout))

    for band_key in ("header", "footer"):
        band = prepared.get(band_key, {})
        if not band.get("enabled"):
            continue

        cells = [
            _prepare_page_layout_cell(cell, request, page_layout=prepared, band=band_key)
            for cell in band.get("cells", [])
        ]
        prepared_band = {**band, "cells": cells}
        if band_key == "header":
            prepared_band["extra_rows"] = [
                _prepare_page_layout_extra_row(row, request)
                for row in band.get("extra_rows", [])
            ]
        prepared[band_key] = prepared_band

    return prepared


def _prepare_page_layout_extra_row(row: dict[str, Any], request: HttpRequest) -> dict[str, Any]:
    """Sanitiza linha extra do cabeçalho para leitura e PDF."""
    prepared = dict(row)
    if prepared.get("type") == "text":
        prepared["text"] = sanitize_header_text_html(str(prepared.get("text", "")))
    return prepared


def _prepare_page_layout_cell(
    cell: dict[str, Any],
    request: HttpRequest,
    *,
    page_layout: dict[str, Any] | None = None,
    band: str = "header",
) -> dict[str, Any]:
    """Sanitiza célula de faixa de layout e resolve URL absoluta de logos."""
    prepared = prepare_logo_cell_for_document(cell, page_layout, band=band)
    if prepared.get("type") == "logo" and prepared.get("url"):
        prepared["url"] = _absolute_url(request, prepared["url"])
    if prepared.get("type") == "text":
        prepared["text"] = sanitize_header_text_html(str(prepared.get("text", "")))
    return prepared
