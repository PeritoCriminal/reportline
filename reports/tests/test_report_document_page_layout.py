# reportline/reports/tests/test_report_document_page_layout.py
"""
Testes de renderização de cabeçalho/rodapé no documento de leitura.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from reports.models import Report
from reports.services.report_document_context import build_report_document_context
from reports.services.report_document_page_layout import (
    format_page_number_label,
    footer_layout_shows_page_number,
    page_layout_band_enabled,
    render_page_footer_read_html,
    render_page_header_read_html,
)
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    apply_footer_template,
    apply_header_template,
)

User = get_user_model()


class ReportDocumentPageLayoutTests(TestCase):
    """Testes de fragmentos read-only de cabeçalho e rodapé."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="document_page_layout",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Layout")
        cls.factory = RequestFactory()

    def _request(self):
        return self.factory.get("/reports/preview/")

    def test_format_page_number_label(self):
        """Garante rótulo de numeração em português com total mínimo coerente."""
        self.assertEqual(format_page_number_label(2, 5), "Página 2 de 5")
        self.assertEqual(format_page_number_label(1, 0), "Página 1 de 1")

    def test_page_layout_band_enabled(self):
        """Garante detecção de faixas ativas no layout de página."""
        layout = apply_header_template({}, "logo_left_text_right")
        self.assertTrue(page_layout_band_enabled(layout, "header"))
        self.assertFalse(page_layout_band_enabled(layout, "footer"))

    def test_footer_layout_shows_page_number_when_enabled(self):
        """Garante detecção de numeração ativa em célula de texto do rodapé."""
        layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        self.assertTrue(footer_layout_shows_page_number(layout))

        layout["footer"]["cells"][0]["show_page_number"] = False
        self.assertFalse(footer_layout_shows_page_number(layout))

    def test_render_page_header_read_html_when_enabled(self):
        """Garante HTML read-only do cabeçalho sem atributos de edição."""
        layout = apply_header_template({}, "logo_left_text_right")
        layout["header"]["cells"][1]["text"] = "Instituto de Criminalística"
        self.report.page_layout = layout
        self.report.save(update_fields=["page_layout"])

        context = build_report_document_context(self.report, self._request())
        html = render_page_header_read_html(context["page_layout"], self._request())

        self.assertIn("report-page-header--read", html)
        self.assertIn("Instituto de Criminalística", html)
        self.assertNotIn("contenteditable", html)

    def test_render_page_footer_read_html_includes_page_number(self):
        """Garante numeração Página N de T no rodapé de leitura."""
        layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        layout["footer"]["cells"][0]["text"] = "Contato"
        self.report.page_layout = layout
        self.report.save(update_fields=["page_layout"])

        context = build_report_document_context(self.report, self._request())
        html = render_page_footer_read_html(
            context["page_layout"],
            self._request(),
            page_number=2,
            page_count=4,
        )

        self.assertIn("report-page-footer--read", html)
        self.assertIn("Contato", html)
        self.assertIn("data-report-page-current", html)
        self.assertIn("data-report-page-total", html)
        self.assertIn(">2<", html)
        self.assertIn(">4<", html)
        self.assertIn("Página", html)
        self.assertIn("report-document-page-number", html)
        self.assertIn("report-page-footer-disclaimer", html)
        self.assertIn('data-text-align="center"', html)
        self.assertIn('style="text-align: center;"', html)

    def test_render_page_footer_read_html_empty_when_disabled(self):
        """Garante ausência de markup quando rodapé está desativado."""
        html = render_page_footer_read_html({"footer": {"enabled": False}}, self._request())
        self.assertEqual(html.strip(), "")
