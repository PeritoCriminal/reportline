"""
Testes da view de edição de relatório.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode

User = get_user_model()


class ReportEditorViewTests(TestCase):
    """Testes da tela de edição visual de relatórios."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório e usuários autor e estranho."""
        cls.author = User.objects.create_user(
            username="autor_editor",
            password="senha-segura",
        )
        cls.other_user = User.objects.create_user(
            username="outro_usuario",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Relatório pericial",
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

    def _edit_url(self):
        """Retorna URL nomeada de edição do relatório de teste."""
        return reverse("reports:edit", kwargs={"pk": self.report.pk})

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes não autenticados."""
        response = self.client.get(self._edit_url())
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self._edit_url()}",
        )

    def test_non_author_receives_404(self):
        """Garante 404 para usuário autenticado que não é autor do relatório."""
        self.client.login(username="outro_usuario", password="senha-segura")
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 404)

    def test_author_sees_editor_layout(self):
        """Garante que o autor veja toolbar, sumário e corpo do relatório."""
        self.client.login(username="autor_editor", password="senha-segura")
        response = self.client.get(self._edit_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relatório pericial")
        self.assertContains(response, "Sumário")
        self.assertContains(response, "Histórico")
        self.assertContains(response, "Descrição dos fatos.")
        self.assertContains(response, 'data-block-type="heading"')
        self.assertContains(response, "contenteditable")
        self.assertContains(response, "report-editor-page")

    def test_empty_report_bootstraps_heading_with_autofocus(self):
        """Garante título H1 vazio com foco quando relatório não possui blocos."""
        empty_report = Report.objects.create(
            author=self.author,
            title="Sem conteúdo",
        )
        self.client.login(username="autor_editor", password="senha-segura")
        response = self.client.get(
            reverse("reports:edit", kwargs={"pk": empty_report.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(empty_report.nodes.count(), 1)
        self.assertContains(response, 'data-block-type="heading"')
        self.assertContains(response, 'data-autofocus="true"')
        self.assertContains(response, "contenteditable")
        self.assertContains(response, "report-editor-outline-root")
        self.assertContains(response, "report_outline_sync.js")

    def test_outline_endpoint_returns_tree_html(self):
        """Garante HTML atualizado do sumário via GET JSON."""
        self.client.login(username="autor_editor", password="senha-segura")
        response = self.client.get(
            reverse("reports:outline", kwargs={"pk": self.report.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("html", payload)
        self.assertIn("Histórico", payload["html"])
        self.assertIn("report-editor-outline", payload["html"])

    def test_outline_endpoint_rejects_non_author(self):
        """Garante bloqueio do sumário assíncrono para usuário estranho."""
        self.client.login(username="outro_usuario", password="senha-segura")
        response = self.client.get(
            reverse("reports:outline", kwargs={"pk": self.report.pk}),
        )

        self.assertEqual(response.status_code, 404)
