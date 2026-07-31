"""
Testes da view de criação de relatório.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportStatus

User = get_user_model()


class ReportCreateViewTests(TestCase):
    """Testes do formulário de novo relatório."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuário autenticável para os cenários."""
        cls.user = User.objects.create_user(
            username="novo_relatorio",
            password="senha-segura",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes não autenticados."""
        response = self.client.get(reverse("reports:new"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('reports:new')}",
        )

    def test_authenticated_user_sees_create_form(self):
        """Garante exibição do formulário de título para usuário autenticado."""
        self.client.login(username="novo_relatorio", password="senha-segura")
        response = self.client.get(reverse("reports:new"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo relatório")
        self.assertContains(response, "Título do relatório")

    def test_valid_submission_creates_report_and_redirects_to_editor(self):
        """Garante criação do relatório e redirecionamento ao editor."""
        self.client.login(username="novo_relatorio", password="senha-segura")
        response = self.client.post(
            reverse("reports:new"),
            {"title": "Laudo de veículo"},
        )

        report = Report.objects.get(title="Laudo de veículo")
        self.assertEqual(report.author, self.user)
        self.assertEqual(report.status, ReportStatus.DRAFT)
        self.assertRedirects(
            response,
            reverse("reports:edit", kwargs={"pk": report.pk}),
        )

    def test_missing_title_shows_inline_error(self):
        """Garante erro inline quando título não é informado."""
        self.client.login(username="novo_relatorio", password="senha-segura")
        response = self.client.post(reverse("reports:new"), {"title": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")
        self.assertEqual(Report.objects.count(), 0)
