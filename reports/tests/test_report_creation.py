# reportline/reports/tests/test_report_creation.py
"""
Testes do serviço de criação de relatórios.
"""

from django.contrib.auth import get_user_model

from django.test import TestCase

from reports.models import ReportStatus
from reports.services.report_creation import create_report

User = get_user_model()


class ReportCreationServiceTests(TestCase):
    """Testes da criação inicial de relatórios em rascunho."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuário autor para os cenários."""
        cls.author = User.objects.create_user(
            username="criador1",
            password="senha-segura",
            first_name="Ana",
            last_name="Costa",
        )

    def test_create_report_persists_draft_with_author(self):
        """Garante relatório criado em rascunho vinculado ao autor informado."""
        report = create_report(author=self.author, title="  Laudo inicial  ")

        self.assertEqual(report.title, "Laudo inicial")
        self.assertEqual(report.status, ReportStatus.DRAFT)
        self.assertEqual(report.author, self.author)

    def test_create_report_populates_author_snapshot(self):
        """Garante snapshot textual do autor ao criar relatório."""
        report = create_report(author=self.author, title="Com snapshot")

        self.assertEqual(report.author_username, "criador1")
        self.assertEqual(report.author_display_name, "Ana Costa")
