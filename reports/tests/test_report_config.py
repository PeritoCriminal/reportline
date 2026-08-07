# reportline/reports/tests/test_report_config.py
"""Testes de configuração de laudo e preferências do usuário."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode, ReportUserConfig
from reports.services.report_config import apply_first_line_indent_to_report, update_report_config
from reports.services.report_creation import create_report
from reports.services.report_heading_numbering import build_heading_number_map_for_report
from reports.services.report_user_config import get_or_create_user_config

User = get_user_model()


class ReportUserConfigTests(TestCase):
    """Testes de defaults por usuário e cópia para laudos novos."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="config_user",
            password="senha-segura",
        )

    def test_create_report_copies_user_defaults(self):
        """Garante cópia das preferências do usuário ao criar laudo."""
        user_config = get_or_create_user_config(self.author)
        user_config.number_headings = False
        user_config.number_captions = True
        user_config.first_line_indent = False
        user_config.save()

        report = create_report(author=self.author, title="Novo laudo")

        self.assertFalse(report.number_headings)
        self.assertTrue(report.number_captions)
        self.assertFalse(report.first_line_indent)

    def test_get_or_create_user_config_uses_defaults(self):
        """Garante criação automática de configuração com valores padrão."""
        config = get_or_create_user_config(self.author)

        self.assertTrue(config.number_headings)
        self.assertFalse(config.number_captions)
        self.assertTrue(config.first_line_indent)
        self.assertEqual(ReportUserConfig.objects.filter(user=self.author).count(), 1)


class ReportConfigServiceTests(TestCase):
    """Testes de persistência e efeitos da configuração no laudo aberto."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="config_service",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Config")

    def _create_body_paragraph(self, *, first_line_indent: bool = True):
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Parágrafo"},
            first_line_indent=first_line_indent,
        )
        return ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("1"),
        )

    def test_update_report_config_syncs_user_preferences(self):
        """Garante que salvar configuração atualiza laudo e preferências do usuário."""
        update_report_config(
            self.report,
            self.author,
            number_headings=False,
            number_captions=True,
            first_line_indent=False,
        )

        self.report.refresh_from_db()
        user_config = ReportUserConfig.objects.get(user=self.author)

        self.assertFalse(self.report.number_headings)
        self.assertTrue(self.report.number_captions)
        self.assertFalse(self.report.first_line_indent)
        self.assertFalse(user_config.number_headings)
        self.assertTrue(user_config.number_captions)
        self.assertFalse(user_config.first_line_indent)

    def test_apply_first_line_indent_updates_all_body_paragraphs(self):
        """Garante recuo propagado a todos os parágrafos de corpo do laudo aberto."""
        node = self._create_body_paragraph(first_line_indent=True)
        self.report.first_line_indent = False

        apply_first_line_indent_to_report(self.report)

        node.block.refresh_from_db()
        self.assertFalse(node.block.first_line_indent)

    def test_number_headings_false_disables_heading_numbers(self):
        """Garante numeração de títulos desligada conforme config do laudo."""
        heading = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Intro"},
            title_level=0,
        )
        ReportNode.objects.create(
            report=self.report,
            block=heading,
            position=Decimal("1"),
        )
        second = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Seção"},
            title_level=0,
        )
        ReportNode.objects.create(
            report=self.report,
            block=second,
            position=Decimal("2"),
        )
        self.report.number_headings = False

        numbers = build_heading_number_map_for_report(self.report)

        self.assertEqual(numbers, {})
