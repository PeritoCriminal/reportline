"""
Renderização de cabeçalho e rodapé para preview paginado e PDF.

Converte ``page_layout`` do laudo em HTML read-only com numeração
``Página N de T`` quando configurada no rodapé.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.template.loader import render_to_string

from reports.services.report_page_layout import footer_text_cell_shows_page_number


def format_page_number_label(page_number: int, page_count: int) -> str:
    """Formata rótulo de numeração de páginas em português."""
    safe_page = max(1, int(page_number))
    safe_total = max(safe_page, int(page_count))
    return f"Página {safe_page} de {safe_total}"


def page_layout_band_enabled(page_layout: dict[str, Any] | None, band: str) -> bool:
    """Indica se cabeçalho ou rodapé está ativo no layout de página."""
    if band not in {"header", "footer"}:
        return False
    if not isinstance(page_layout, dict):
        return False
    band_layout = page_layout.get(band, {})
    return bool(isinstance(band_layout, dict) and band_layout.get("enabled"))


def footer_layout_shows_page_number(page_layout: dict[str, Any] | None) -> bool:
    """Indica se alguma célula de texto do rodapé exibe numeração de páginas."""
    if not page_layout_band_enabled(page_layout, "footer"):
        return False
    footer = page_layout.get("footer", {})
    for cell in footer.get("cells", []):
        if footer_text_cell_shows_page_number(cell):
            return True
    return False


def render_page_header_read_html(page_layout: dict[str, Any], request: HttpRequest) -> str:
    """Renderiza partial HTML do cabeçalho para leitura/preview."""
    return render_to_string(
        "reports/includes/report_page_header_read.html",
        {"page_layout": page_layout},
        request=request,
    )


def render_page_footer_read_html(
    page_layout: dict[str, Any],
    request: HttpRequest,
    *,
    page_number: int = 1,
    page_count: int = 1,
) -> str:
    """Renderiza partial HTML do rodapé com numeração opcional."""
    return render_to_string(
        "reports/includes/report_page_footer_read.html",
        {
            "page_layout": page_layout,
            "page_number": page_number,
            "page_count": page_count,
        },
        request=request,
    )


def render_page_footer_read_html_for_page(
    page_layout: dict[str, Any],
    request: HttpRequest,
    *,
    page_number: int,
    page_count: int,
) -> str:
    """Renderiza rodapé de uma página específica com numeração resolvida."""
    return render_page_footer_read_html(
        page_layout,
        request,
        page_number=page_number,
        page_count=page_count,
    )
