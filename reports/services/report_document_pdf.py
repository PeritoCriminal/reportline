"""
Geração de PDF do laudo via Playwright + Chromium.

Monta HTML canônico de leitura (sem paginação JS) e exporta bytes PDF com
cabeçalho/rodapé repetidos conforme ``page_layout``.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.text import slugify

from reports.models import Report
from reports.services.report_document_context import build_report_document_context
from reports.services.report_document_pdf_fragments import (
    ReportPdfUnavailable,
    build_playwright_footer_template,
    build_playwright_header_template,
    playwright_display_header_footer,
)

ABNT_PDF_MARGINS = {
    "top": "3cm",
    "right": "2cm",
    "bottom": "2cm",
    "left": "3cm",
}


def is_playwright_available() -> bool:
    """Indica se o pacote Playwright está instalado no ambiente."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def build_report_document_pdf_context(report: Report, request: HttpRequest) -> dict:
    """Monta contexto de leitura sem script de paginação do preview."""
    context = build_report_document_context(report, request)
    context.pop("document_script", None)
    return context


def build_report_document_html(report: Report, request: HttpRequest) -> str:
    """Renderiza HTML contínuo enviado ao Chromium para exportação PDF."""
    context = build_report_document_pdf_context(report, request)
    return render_to_string(
        "reports/document/report_document_pdf.html",
        context,
        request=request,
    )


def pdf_download_filename(report: Report) -> str:
    """Deriva nome de arquivo seguro para Content-Disposition."""
    slug = slugify(report.title) or "laudo"
    return f"{slug}.pdf"


def render_report_document_pdf_bytes(report: Report, request: HttpRequest) -> bytes:
    """
    Gera bytes PDF do laudo via Playwright.

    Raises:
        ReportPdfUnavailable: quando Playwright/Chromium não estão disponíveis.
    """
    if not is_playwright_available():
        raise ReportPdfUnavailable("Playwright não está instalado neste ambiente.")

    html = build_report_document_html(report, request)
    page_layout = build_report_document_pdf_context(report, request)["page_layout"]
    header_template = build_playwright_header_template(page_layout, request)
    footer_template = build_playwright_footer_template(page_layout, request)
    display_header_footer = playwright_display_header_footer(page_layout)

    return _render_pdf_with_playwright(
        html,
        request,
        header_template=header_template,
        footer_template=footer_template,
        display_header_footer=display_header_footer,
    )


def _render_pdf_with_playwright(
    html: str,
    request: HttpRequest,
    *,
    header_template: str,
    footer_template: str,
    display_header_footer: bool,
) -> bytes:
    """Executa Chromium headless e retorna bytes do PDF."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ReportPdfUnavailable("Playwright não está instalado neste ambiente.") from exc

    base_url = request.build_absolute_uri("/")

    try:
        with sync_playwright() as playwright_context:
            browser = playwright_context.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load", base_url=base_url)
                return page.pdf(
                    format="A4",
                    margin=ABNT_PDF_MARGINS,
                    display_header_footer=display_header_footer,
                    header_template=header_template,
                    footer_template=footer_template,
                    print_background=True,
                )
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise ReportPdfUnavailable(
            "Chromium não está disponível. Execute `playwright install chromium`."
        ) from exc
