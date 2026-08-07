# reportline/reports/tests/test_report_deletion.py
"""
Testes do serviço de exclusão permanente de relatório e limpeza de mídia.
"""

import shutil
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from reports.models import Report, ReportBlock, ReportBlockType, ReportImage, ReportNode
from reports.services.report_deletion import delete_report
from reports.services.report_image_upload import build_image_block_content, store_report_image
from reports.services.report_media_cleanup import report_media_folder_relative_path

User = get_user_model()


@override_settings(MEDIA_ROOT="test_media_report_deletion")
class ReportMediaFolderDeletionTests(TestCase):
    """Testes da remoção da pasta de mídia ao excluir um laudo."""

    def setUp(self):
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            shutil.rmtree(media_root)

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="media_cleanup_author",
            password="senha-segura",
        )

    def _build_image_upload(self):
        buffer = BytesIO()
        Image.new("RGB", (400, 300), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("sample.jpg", buffer.read(), content_type="image/jpeg")

    def test_delete_report_removes_media_folder_and_orphan_files(self):
        """Garante exclusão da pasta do laudo em MEDIA com todo o conteúdo."""
        report = Report.objects.create(author=self.author, title="Laudo com mídia")
        report_image = store_report_image(report, self._build_image_upload())
        folder_path = report_media_folder_relative_path(report.pk)

        block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content=build_image_block_content(report_image),
        )
        ReportNode.objects.create(
            report=report,
            block=block,
            position=Decimal("1"),
        )

        orphan_path = f"{folder_path}/orphan.txt"
        default_storage.save(orphan_path, ContentFile(b"arquivo residual"))

        self.assertTrue(default_storage.exists(report_image.image.name))
        self.assertTrue(default_storage.exists(orphan_path))
        self.assertTrue(default_storage.exists(folder_path))

        delete_report(report)

        self.assertFalse(default_storage.exists(folder_path))
        self.assertFalse(default_storage.exists(report_image.image.name))
        self.assertFalse(default_storage.exists(orphan_path))

    def test_delete_report_without_media_folder_does_not_fail(self):
        """Garante exclusão segura quando o laudo não possui pasta em MEDIA."""
        report = Report.objects.create(author=self.author, title="Laudo sem mídia")
        folder_path = report_media_folder_relative_path(report.pk)

        self.assertFalse(default_storage.exists(folder_path))

        delete_report(report)

        self.assertFalse(Report.objects.filter(pk=report.pk).exists())
        self.assertFalse(default_storage.exists(folder_path))

    def test_delete_report_removes_empty_media_folder_after_image_files(self):
        """Garante remoção da pasta UUID mesmo após apagar só os arquivos de imagem."""
        report = Report.objects.create(author=self.author, title="Laudo pasta vazia")
        store_report_image(report, self._build_image_upload())
        folder_path = report_media_folder_relative_path(report.pk)

        self.assertTrue(default_storage.exists(folder_path))

        delete_report(report)

        self.assertFalse(default_storage.exists(folder_path))

    def test_direct_report_delete_removes_media_folder(self):
        """Garante limpeza da pasta mesmo quando o laudo é excluído via ORM."""
        report = Report.objects.create(author=self.author, title="Laudo ORM")
        store_report_image(report, self._build_image_upload())
        folder_path = report_media_folder_relative_path(report.pk)
        report_id = report.pk

        self.assertTrue(default_storage.exists(folder_path))

        report.delete()

        self.assertFalse(Report.objects.filter(pk=report_id).exists())
        self.assertFalse(default_storage.exists(folder_path))
