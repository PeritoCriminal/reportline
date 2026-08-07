# reportline/reports/tests/test_report_image_upload_api.py
"""
Testes do endpoint de upload de imagens do editor.
"""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from reports.models import Report, ReportImage
from reports.services.report_image_processing import MAX_IMAGE_SIDE_PX

User = get_user_model()


class ReportImageUploadApiTests(TestCase):
    """Testes de POST multipart para imagens do relatório."""

    @classmethod
    def setUpTestData(cls):
        """Prepara autor, intruso e relatório de teste."""
        cls.author = User.objects.create_user(
            username="image_author",
            password="senha-segura",
        )
        cls.other = User.objects.create_user(
            username="image_intruder",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Imagens")

    def _build_image_file(self, size: tuple[int, int] = (800, 600)) -> SimpleUploadedFile:
        """Monta upload JPEG em memória."""
        buffer = BytesIO()
        Image.new("RGB", size, color="orange").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("foto.jpg", buffer.read(), content_type="image/jpeg")

    def _post_upload(self, file_obj, user="image_author"):
        """Executa POST no endpoint de upload."""
        self.client.login(username=user, password="senha-segura")
        return self.client.post(
            reverse("reports:image_upload", kwargs={"pk": self.report.pk}),
            data={"image": file_obj},
        )

    def test_upload_returns_image_metadata(self):
        """Garante resposta JSON com metadados para montar bloco de imagem."""
        response = self._post_upload(self._build_image_file((1200, 800)))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("image_id", payload)
        self.assertIn("file", payload)
        self.assertIn("url", payload)
        self.assertEqual(max(payload["width"], payload["height"]), MAX_IMAGE_SIDE_PX)

        report_image = ReportImage.objects.get(pk=payload["image_id"])
        self.assertEqual(report_image.report_id, self.report.pk)

    def test_upload_rejects_non_author(self):
        """Garante 404 para usuário que não é autor do relatório."""
        response = self._post_upload(self._build_image_file(), user="image_intruder")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(ReportImage.objects.count(), 0)

    def test_upload_requires_file(self):
        """Garante erro quando campo image não é enviado."""
        self.client.login(username="image_author", password="senha-segura")
        response = self.client.post(
            reverse("reports:image_upload", kwargs={"pk": self.report.pk}),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("errors", response.json())
