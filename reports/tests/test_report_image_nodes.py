# reportline/reports/tests/test_report_image_nodes.py
"""Testes da inserção de blocos nativos IMAGE + legenda."""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_caption_numbering import build_caption_number_map
from reports.services.report_editor_context import _group_nodes_by_parent
from reports.services.report_image_nodes import insert_report_image_nodes
from reports.services.report_image_upload import store_report_image
from reports.services.report_tree import insert_sibling_after

User = get_user_model()


class ReportImageNodesTests(TestCase):
    """Testes de inserção de pares IMAGE + legenda."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="report_image_nodes",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Imagens", number_captions=True)

    def _store_test_image(self, *, color: str, name: str):
        buffer = BytesIO()
        Image.new("RGB", (24, 24), color=color).save(buffer, format="JPEG")
        buffer.seek(0)
        uploaded = SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")
        return store_report_image(self.report, uploaded)

    def _make_anchor(self) -> ReportNode:
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Parágrafo base."},
        )
        return ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("1"),
        )

    def test_insert_uses_em_dash_placeholder_when_caption_empty(self):
        """Garante travessão mínimo na legenda vazia para numeração Figura N."""
        image = self._store_test_image(color="red", name="a.jpg")
        anchor = self._make_anchor()

        class Ctx:
            report = self.report
            anchor_node = anchor

        def inserter(ctx, *, block_type, content, title_level=0, text_align=None, first_line_indent=None, is_caption=False):
            node = insert_sibling_after(
                ctx.report,
                ctx.anchor_node,
                block_type=block_type,
                content=content,
                first_line_indent=first_line_indent,
                is_caption=is_caption,
            )
            ctx.anchor_node = node
            return node

        insert_report_image_nodes(
            Ctx(),
            [{"image_id": str(image.pk), "caption": ""}],
            insert_node=inserter,
        )

        nodes = list(self.report.nodes.select_related("block").order_by("position", "created_at"))
        image_index = next(i for i, node in enumerate(nodes) if node.block.block_type == ReportBlockType.IMAGE)
        caption_node = nodes[image_index + 1]
        self.assertEqual(caption_node.block.block_type, ReportBlockType.PARAGRAPH)
        self.assertEqual(caption_node.block.content.get("text"), "—")
        self.assertEqual(caption_node.block.text_align, "center")
        self.assertFalse(caption_node.block.first_line_indent)

        nodes_by_parent = _group_nodes_by_parent(nodes)
        numbers = build_caption_number_map(nodes_by_parent, number_captions=True)
        self.assertEqual(numbers[caption_node.pk], 1)

    def test_insert_preserves_upload_order_for_caption_numbering(self):
        """Garante numeração Figura N na ordem de inserção das imagens."""
        images = [
            self._store_test_image(color="red", name="first.jpg"),
            self._store_test_image(color="green", name="second.jpg"),
            self._store_test_image(color="blue", name="third.jpg"),
        ]
        anchor = self._make_anchor()

        class Ctx:
            report = self.report
            anchor_node = anchor

        def inserter(ctx, *, block_type, content, title_level=0, text_align=None, first_line_indent=None, is_caption=False):
            node = insert_sibling_after(
                ctx.report,
                ctx.anchor_node,
                block_type=block_type,
                content=content,
                first_line_indent=first_line_indent,
                is_caption=is_caption,
            )
            ctx.anchor_node = node
            return node

        insert_report_image_nodes(
            Ctx(),
            [
                {"image_id": str(images[0].pk), "caption": "Primeira figura."},
                {"image_id": str(images[1].pk), "caption": "Segunda figura."},
                {"image_id": str(images[2].pk), "caption": "Terceira figura."},
            ],
            insert_node=inserter,
        )

        nodes = list(self.report.nodes.select_related("block").order_by("position", "created_at"))
        nodes_by_parent = _group_nodes_by_parent(nodes)
        numbers = build_caption_number_map(nodes_by_parent, number_captions=True)

        caption_nodes = [
            node
            for node in nodes
            if node.block.block_type == ReportBlockType.PARAGRAPH
            and node.block.content.get("text") in {
                "Primeira figura.",
                "Segunda figura.",
                "Terceira figura.",
            }
        ]
        self.assertEqual(len(caption_nodes), 3)
        self.assertEqual(numbers[caption_nodes[0].pk], 1)
        self.assertEqual(numbers[caption_nodes[1].pk], 2)
        self.assertEqual(numbers[caption_nodes[2].pk], 3)
