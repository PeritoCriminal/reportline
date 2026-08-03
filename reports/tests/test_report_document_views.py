"""
Testes da view de preview de documento do relatório.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    apply_footer_template,
    apply_header_template,
    update_logo_cell_from_image,
)

User = get_user_model()


class ReportDocumentPreviewViewTests(TestCase):
    """Testes da visualização read-only do laudo para o autor."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório com conteúdo e usuários autor e estranho."""
        cls.author = User.objects.create_user(
            username="autor_preview",
            password="senha-segura",
        )
        cls.other_user = User.objects.create_user(
            username="outro_preview",
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
        paragraph_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Descrição dos fatos."},
        )
        ReportNode.objects.create(
            report=cls.report,
            block=paragraph_block,
            position=Decimal("2"),
        )

    def _preview_url(self, report=None):
        """Retorna URL nomeada de preview do relatório informado."""
        target = report or self.report
        return reverse("reports:preview", kwargs={"pk": target.pk})

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes não autenticados."""
        response = self.client.get(self._preview_url())
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self._preview_url()}",
        )

    def test_non_author_receives_404(self):
        """Garante 404 para usuário autenticado que não é autor do relatório."""
        self.client.login(username="outro_preview", password="senha-segura")
        response = self.client.get(self._preview_url())
        self.assertEqual(response.status_code, 404)

    def test_author_sees_document_preview(self):
        """Garante HTML de leitura autônomo com conteúdo do laudo para o autor."""
        self.client.login(username="autor_preview", password="senha-segura")
        response = self.client.get(self._preview_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "report-document-preview")
        self.assertContains(response, "report-document-pages")
        self.assertContains(response, "report-document-pagination-source")
        self.assertContains(response, "report-document-page-sheet")
        self.assertContains(response, "paginateDocument")
        self.assertContains(response, "Histórico")
        self.assertContains(response, "Descrição dos fatos.")
        self.assertContains(response, "report-document-block")
        self.assertContains(response, "<style>")
        self.assertContains(response, "Times New Roman")
        self.assertNotContains(response, "contenteditable")
        self.assertNotContains(response, "report-editor-toolbar")

    def test_empty_report_shows_placeholder_without_bootstrap(self):
        """Garante mensagem de laudo vazio sem criar blocos de bootstrap do editor."""
        empty_report = Report.objects.create(
            author=self.author,
            title="Sem conteúdo",
        )
        self.client.login(username="autor_preview", password="senha-segura")
        response = self.client.get(self._preview_url(empty_report))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(empty_report.nodes.count(), 0)
        self.assertContains(response, "Este laudo ainda não possui conteúdo.")
        self.assertNotContains(response, "contenteditable")

    def test_preview_renders_footer_with_page_number_template(self):
        """Garante rodapé read-only com template de numeração no preview."""
        layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        layout["footer"]["cells"][0]["text"] = "Secretaria"
        self.report.page_layout = layout
        self.report.save(update_fields=["page_layout"])

        self.client.login(username="autor_preview", password="senha-segura")
        response = self.client.get(self._preview_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "report-page-footer--read")
        self.assertContains(response, "Secretaria")
        self.assertContains(response, "data-report-page-current")
        self.assertContains(response, "data-report-page-total")
        self.assertContains(response, "report-document-footer-template")

    def test_preview_renders_page_header_template_when_enabled(self):
        """Garante template de cabeçalho disponível para paginação do preview."""
        layout = apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": "reports/1/logo.png",
                "image_id": "logo-1",
                "width": 400,
                "height": 200,
                "alt": "Brasão",
            },
        )
        layout["header"]["cells"][1]["text"] = "Instituto de Criminalística"
        self.report.page_layout = layout
        self.report.save(update_fields=["page_layout"])

        self.client.login(username="autor_preview", password="senha-segura")
        response = self.client.get(self._preview_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "report-document-header-template")
        self.assertContains(response, "report-document-page-header")
        self.assertContains(response, "Instituto de Criminalística")
        self.assertContains(response, "reports/1/logo.png")
        self.assertNotContains(response, "contenteditable")
