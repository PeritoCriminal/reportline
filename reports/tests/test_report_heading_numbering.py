"""
Testes da numeração automática de títulos.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_editor_context import build_report_editor_context
from reports.services.report_heading_numbering import build_heading_number_map_for_report

User = get_user_model()


class ReportHeadingNumberingTests(TestCase):
    """Testes da sequência hierárquica 1, 1.1, 1.1.1 por title_level."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="numbering_user",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Numeração")

    def _create_heading(self, text, *, level=0, parent=None, position=Decimal("1")):
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": text},
            title_level=level,
        )
        return ReportNode.objects.create(
            report=self.report,
            parent=parent,
            block=block,
            position=position,
        )

    def test_numbers_follow_title_levels_in_reading_order(self):
        """Garante sequência 1, 1.1, 1.2, 2 conforme níveis e ordem de leitura."""
        first = self._create_heading("Introdução", level=0, position=Decimal("1"))
        self._create_heading("Detalhe", level=1, parent=first, position=Decimal("1"))
        self._create_heading("Subdetalhe", level=1, parent=first, position=Decimal("2"))
        self._create_heading("Conclusão", level=0, position=Decimal("2"))

        numbers = build_heading_number_map_for_report(self.report)

        nodes = list(self.report.nodes.order_by("position"))
        intro = next(node for node in nodes if node.block.content["text"] == "Introdução")
        detail = next(node for node in nodes if node.block.content["text"] == "Detalhe")
        subdetail = next(node for node in nodes if node.block.content["text"] == "Subdetalhe")
        conclusion = next(node for node in nodes if node.block.content["text"] == "Conclusão")

        self.assertEqual(numbers[intro.pk], "")
        self.assertEqual(numbers[detail.pk], "1.1")
        self.assertEqual(numbers[subdetail.pk], "1.2")
        self.assertEqual(numbers[conclusion.pk], "2")

    def test_first_heading_in_report_is_not_numbered(self):
        """Garante título principal sem numeração automática."""
        only = self._create_heading("Laudo pericial", level=0)

        numbers = build_heading_number_map_for_report(self.report)

        self.assertEqual(numbers[only.pk], "")

    def test_skipped_level_gets_implicit_parent_number(self):
        """Garante numeração 1.1.1 ao pular nível intermediário após título principal."""
        self._create_heading("Título principal", level=0, position=Decimal("1"))
        deep = self._create_heading("Subseção profunda", level=2, position=Decimal("2"))

        numbers = build_heading_number_map_for_report(self.report)

        self.assertEqual(numbers[deep.pk], "1.1.1")

    def test_editor_context_exposes_heading_numbers(self):
        """Garante mapa de numeração no contexto do editor."""
        self._create_heading("Capítulo", level=0)

        context = build_report_editor_context(self.report)

        self.assertEqual(len(context["heading_numbers"]), 1)
        self.assertEqual(context["outline_tree"][0].number, "")
        self.assertEqual(context["body_entries"][0].heading_number, "")
