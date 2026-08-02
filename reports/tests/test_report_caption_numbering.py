"""Testes de numeração automática de legendas de imagem."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_caption_numbering import build_caption_number_map
from reports.services.report_editor_context import _group_nodes_by_parent

User = get_user_model()


class ReportCaptionNumberingTests(TestCase):
    """Testes da sequência Figura N em legendas com texto."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="caption_numbering",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Legendas")

    def _create_image_with_caption(self, *, caption_text: str, position: Decimal):
        image_block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content={"alt": "", "file": "img.jpg", "image_id": "", "width": 100, "height": 80},
        )
        image_node = ReportNode.objects.create(
            report=self.report,
            block=image_block,
            position=position,
        )
        caption_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": caption_text},
            first_line_indent=False,
        )
        caption_node = ReportNode.objects.create(
            report=self.report,
            block=caption_block,
            position=position + Decimal("0.1"),
        )
        return image_node, caption_node

    def _nodes_by_parent(self):
        nodes = list(
            self.report.nodes.select_related("block").order_by("position", "created_at")
        )
        return _group_nodes_by_parent(nodes)

    def test_numbers_only_captions_with_text_in_reading_order(self):
        """Garante numeração sequencial ignorando legendas vazias."""
        _image1, caption1 = self._create_image_with_caption(
            caption_text="Primeira",
            position=Decimal("1"),
        )
        self._create_image_with_caption(
            caption_text="",
            position=Decimal("2"),
        )
        _image3, caption3 = self._create_image_with_caption(
            caption_text="Terceira",
            position=Decimal("3"),
        )

        numbers = build_caption_number_map(
            self._nodes_by_parent(),
            number_captions=True,
        )

        self.assertEqual(numbers[caption1.pk], 1)
        self.assertEqual(numbers[caption3.pk], 2)
        self.assertEqual(len(numbers), 2)

    def test_returns_empty_map_when_numbering_disabled(self):
        """Garante mapa vazio quando numeração de legendas está desligada."""
        _image, caption = self._create_image_with_caption(
            caption_text="Legenda",
            position=Decimal("1"),
        )

        numbers = build_caption_number_map(
            self._nodes_by_parent(),
            number_captions=False,
        )

        self.assertEqual(numbers, {})
