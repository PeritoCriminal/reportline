"""
Fragmentos HTML de cabeçalho e rodapé para Playwright PDF.

Converte ``page_layout`` em ``header_template`` / ``footer_template`` com logos
inlined como data URI e numeração via classes nativas do Chromium.
"""

from __future__ import annotations

import base64
import mimetypes
from copy import deepcopy
from typing import Any

from django.core.files.storage import default_storage
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from reports.services.report_document_page_layout import (
    footer_layout_shows_page_number,
    page_layout_band_enabled,
)
from reports.services.report_inline_text import sanitize_header_text_html


PLAYWRIGHT_EMPTY_FRAGMENT = "<div></div>"


class ReportPdfUnavailable(Exception):
    """Indica ausência de Playwright/Chromium para geração de PDF."""


def build_playwright_header_template(
    page_layout: dict[str, Any] | None,
    request: HttpRequest,
) -> str:
    """Monta ``header_template`` do Playwright a partir do layout persistido."""
    if not page_layout_band_enabled(page_layout, "header"):
        return PLAYWRIGHT_EMPTY_FRAGMENT

    header_layout = page_layout.get("header", {})
    cells = _prepare_pdf_band_cells(header_layout)
    extra_rows = _prepare_pdf_header_extra_rows(header_layout)
    if not cells and not extra_rows:
        return PLAYWRIGHT_EMPTY_FRAGMENT

    return render_to_string(
        "reports/includes/report_page_header_pdf_fragment.html",
        {"cells": cells, "extra_rows": extra_rows},
        request=request,
    )


def build_playwright_footer_template(
    page_layout: dict[str, Any] | None,
    request: HttpRequest,
) -> str:
    """Monta ``footer_template`` do Playwright com numeração quando configurada."""
    if not page_layout_band_enabled(page_layout, "footer"):
        return PLAYWRIGHT_EMPTY_FRAGMENT

    cells = _prepare_pdf_band_cells(page_layout.get("footer", {}))
    if not cells:
        return PLAYWRIGHT_EMPTY_FRAGMENT

    return render_to_string(
        "reports/includes/report_page_footer_pdf_fragment.html",
        {
            "cells": cells,
            "shows_page_number": footer_layout_shows_page_number(page_layout),
        },
        request=request,
    )


def playwright_display_header_footer(page_layout: dict[str, Any] | None) -> bool:
    """Indica se cabeçalho ou rodapé devem ser repetidos no PDF."""
    return page_layout_band_enabled(page_layout, "header") or page_layout_band_enabled(
        page_layout,
        "footer",
    )


def logo_cell_data_uri(cell: dict[str, Any]) -> str:
    """Converte arquivo de logo da célula em data URI para fragmentos Playwright."""
    file_path = str(cell.get("file", "")).strip()
    if not file_path or not default_storage.exists(file_path):
        return ""

    with default_storage.open(file_path, "rb") as stored_file:
        payload = stored_file.read()

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _prepare_pdf_band_cells(band_layout: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza células de faixa para templates PDF com logos inlined."""
    prepared_cells: list[dict[str, Any]] = []
    for cell in band_layout.get("cells", []):
        if not isinstance(cell, dict):
            continue

        prepared = deepcopy(cell)
        if prepared.get("type") == "logo":
            prepared["logo_data_uri"] = logo_cell_data_uri(prepared)
            if not prepared["logo_data_uri"]:
                continue
        elif prepared.get("type") == "text":
            prepared["text_html"] = sanitize_header_text_html(str(prepared.get("text", "")))
            prepared["text_plain"] = strip_tags(prepared["text_html"]).strip()
        else:
            continue

        prepared_cells.append(prepared)

    return prepared_cells


def _prepare_pdf_header_extra_rows(band_layout: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza linhas extras do cabeçalho para o fragmento PDF."""
    prepared_rows: list[dict[str, Any]] = []
    for row in band_layout.get("extra_rows", []):
        if not isinstance(row, dict):
            continue

        prepared = deepcopy(row)
        row_type = prepared.get("type")
        if row_type == "text":
            prepared["text_html"] = sanitize_header_text_html(str(prepared.get("text", "")))
        elif row_type != "rule":
            continue

        prepared_rows.append(prepared)

    return prepared_rows
