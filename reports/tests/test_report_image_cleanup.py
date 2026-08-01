"""
Testes de limpeza de imagens ao excluir blocos.
"""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from reports.models import Report, ReportBlock, ReportBlockType, ReportImage, ReportNode
from reports.services.report_image_upload import build_image_block_content, store_report_image

User = get_user_model()


class ReportImageCleanupTests(TestCase):
    """Testes de exclusão de ReportImage quando nó de imagem é removido."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório com bloco de imagem."""
        cls.author = User.objects.create_user(
            username="cleanup_user",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Cleanup")

    def _create_image_block(self) -> tuple[ReportNode, ReportImage]:
        """Cria bloco de imagem persistido com arquivo."""
        buffer = BytesIO()
        Image.new("RGB", (400, 300), color="purple").save(buffer, format="JPEG")
        buffer.seek(0)
        upload = SimpleUploadedFile("sample.jpg", buffer.read(), content_type="image/jpeg")

        report_image = store_report_image(self.report, upload)
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content=build_image_block_content(report_image),
        )
        node = ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("1"),
        )
        return node, report_image

    def test_delete_image_node_removes_report_image(self):
        """Garante remoção do arquivo persistido ao excluir nó de imagem."""
        node, report_image = self._create_image_block()
        image_id = report_image.pk

        node.delete()

        self.assertFalse(ReportImage.objects.filter(pk=image_id).exists())
        self.assertFalse(ReportBlock.objects.filter(block_type=ReportBlockType.IMAGE).exists())

    def test_delete_table_node_removes_embedded_images(self):
        """Garante remoção de imagens embutidas ao excluir nó de tabela."""
        buffer = BytesIO()
        Image.new("RGB", (200, 100), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        upload = SimpleUploadedFile("sample.jpg", buffer.read(), content_type="image/jpeg")
        report_image = store_report_image(self.report, upload)

        cell_content = build_image_block_content(report_image)
        cell_content["type"] = "image"
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.TABLE,
            content={"headers": ["Col"], "rows": [[cell_content]]},
        )
        node = ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("2"),
        )
        image_id = report_image.pk

        node.delete()

        self.assertFalse(ReportImage.objects.filter(pk=image_id).exists())
