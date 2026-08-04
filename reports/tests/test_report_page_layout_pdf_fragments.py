"""
Testes de fragmentos Playwright para cabeçalho e rodapé do PDF.
"""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from reports.models import Report
from reports.services.report_document_page_layout import footer_layout_shows_page_number
from reports.services.report_document_pdf_fragments import (
    PLAYWRIGHT_EMPTY_FRAGMENT,
    build_playwright_footer_template,
    build_playwright_header_template,
    playwright_display_header_footer,
)
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    apply_footer_template,
    apply_header_template,
)

User = get_user_model()


class ReportPageLayoutPdfFragmentTests(TestCase):
    """Testes de adapter page_layout → header_template/footer_template."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="pdf_fragments",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Fragmentos")
        cls.factory = RequestFactory()

    def _request(self):
        return self.factory.get("/reports/document/")

    def test_empty_fragments_when_bands_disabled(self):
        """Garante fragmento vazio quando cabeçalho e rodapé estão desativados."""
        page_layout = {"header": {"enabled": False}, "footer": {"enabled": False}}

        self.assertEqual(
            build_playwright_header_template(page_layout, self._request()),
            PLAYWRIGHT_EMPTY_FRAGMENT,
        )
        self.assertEqual(
            build_playwright_footer_template(page_layout, self._request()),
            PLAYWRIGHT_EMPTY_FRAGMENT,
        )
        self.assertFalse(playwright_display_header_footer(page_layout))

    def test_footer_fragment_includes_playwright_page_number_classes(self):
        """Garante classes pageNumber/totalPages no rodapé quando numeração está ativa."""
        layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        layout["footer"]["cells"][0]["text"] = "Instituto"

        html = build_playwright_footer_template(layout, self._request())

        self.assertIn('class="pageNumber"', html)
        self.assertIn('class="totalPages"', html)
        self.assertIn("Instituto", html)
        self.assertTrue(footer_layout_shows_page_number(layout))
        self.assertTrue(playwright_display_header_footer(layout))

    def test_header_fragment_renders_extra_rows(self):
        """Garante linhas extras no fragmento PDF do cabeçalho."""
        layout = apply_header_template({}, "logo_left_text_right")
        layout["header"]["extra_rows"] = [
            {"type": "rule"},
            {
                "type": "text",
                "text": "Laudo nº 123",
                "align": "right",
                "indent_level": 0,
                "first_line_indent": False,
                "muted": True,
            },
        ]

        html = build_playwright_header_template(layout, self._request())

        self.assertIn("Laudo nº 123", html)
        self.assertIn("<hr", html)
        self.assertIn("color: #666", html)

    def test_header_fragment_renders_text_cell(self):
        """Garante texto sanitizado no fragmento de cabeçalho."""
        layout = apply_header_template({}, "logo_left_text_right")
        layout["header"]["cells"][1]["text"] = "Instituto de Criminalística"

        html = build_playwright_header_template(layout, self._request())

        self.assertIn("Instituto de Criminalística", html)
        self.assertNotIn("contenteditable", html)
