# reportline/reports/tests/test_report_document_pdf_views.py
"""
Testes da view de exportação PDF do relatório.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_document_pdf_fragments import ReportPdfUnavailable

User = get_user_model()


class ReportDocumentPdfViewTests(TestCase):
    """Testes da rota /document/ (PDF e HTML de debug)."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="autor_pdf",
            password="senha-segura",
        )
        cls.other_user = User.objects.create_user(
            username="outro_pdf",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Laudo pericial",
        )
        heading_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Histórico"},
            title_level=1,
        )
        ReportNode.objects.create(
            report=cls.report,
            block=heading_block,
            position=Decimal("1"),
        )

    def _document_url(self, report=None, *, html=False):
        target = report or self.report
        url = reverse("reports:document", kwargs={"pk": target.pk})
        if html:
            return f"{url}?html=1"
        return url

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes não autenticados."""
        response = self.client.get(self._document_url())
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self._document_url()}",
        )

    def test_non_author_receives_404(self):
        """Garante 404 para usuário autenticado que não é autor do relatório."""
        self.client.login(username="outro_pdf", password="senha-segura")
        response = self.client.get(self._document_url())
        self.assertEqual(response.status_code, 404)

    def test_html_debug_mode_returns_continuous_document(self):
        """Garante HTML contínuo sem paginação JS via ?html=1."""
        self.client.login(username="autor_pdf", password="senha-segura")
        response = self.client.get(self._document_url(html=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertContains(response, "report-document-pdf")
        self.assertContains(response, "Histórico")
        self.assertNotContains(response, "paginateDocument")
        self.assertNotContains(response, 'class="report-document-pagination-source"')
        self.assertNotContains(response, 'id="report-document-pages"')

    @patch(
        "reports.views.report_document_views.render_report_document_pdf_bytes",
        side_effect=ReportPdfUnavailable("indisponível"),
    )
    def test_pdf_unavailable_returns_503(self, _mock_render):
        """Garante página 503 quando Playwright/Chromium não estão disponíveis."""
        self.client.login(username="autor_pdf", password="senha-segura")
        response = self.client.get(self._document_url())

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Exportação de PDF indisponível", status_code=503)

    @patch(
        "reports.views.report_document_views.render_report_document_pdf_bytes",
        return_value=b"%PDF-1.4 mocked",
    )
    def test_author_receives_pdf_inline(self, _mock_render):
        """Garante resposta PDF inline para o autor quando renderização está disponível."""
        self.client.login(username="autor_pdf", password="senha-segura")
        response = self.client.get(self._document_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
