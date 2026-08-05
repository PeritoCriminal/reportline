"""
Testes de redimensionamento de imagens para blocos de relatório.
"""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from reports.services.report_image_processing import (
    MAX_IMAGE_SIDE_PX,
    process_image_bytes,
    process_uploaded_image,
    resize_image_to_max_side,
)


class ReportImageProcessingTests(TestCase):
    """Testes de validação e redimensionamento de uploads."""

    def _build_upload(self, size: tuple[int, int], fmt: str = "JPEG") -> SimpleUploadedFile:
        """Gera arquivo de imagem em memória com dimensões informadas."""
        buffer = BytesIO()
        Image.new("RGB", size, color="red").save(buffer, format=fmt)
        buffer.seek(0)
        content_type = "image/jpeg" if fmt == "JPEG" else f"image/{fmt.lower()}"
        return SimpleUploadedFile(
            f"photo.{fmt.lower()}",
            buffer.read(),
            content_type=content_type,
        )

    def test_resize_reduces_longest_side_to_limit(self):
        """Garante redimensionamento quando maior dimensão excede 14 cm em px."""
        source = Image.new("RGB", (2000, 800), color="blue")
        resized = resize_image_to_max_side(source, MAX_IMAGE_SIDE_PX)

        self.assertEqual(max(resized.size), MAX_IMAGE_SIDE_PX)
        self.assertLess(resized.width, source.width)

    def test_resize_does_not_upscale_small_images(self):
        """Garante que imagens menores que o limite não são ampliadas."""
        source = Image.new("RGB", (200, 100), color="green")
        resized = resize_image_to_max_side(source, MAX_IMAGE_SIDE_PX)

        self.assertEqual(resized.size, source.size)

    def test_process_uploaded_image_returns_dimensions(self):
        """Garante bytes, extensão e dimensões após processamento."""
        upload = self._build_upload((1600, 900))

        image_bytes, extension, width, height = process_uploaded_image(upload)

        self.assertGreater(len(image_bytes), 0)
        self.assertIn(extension, ("jpg", "png"))
        self.assertLessEqual(max(width, height), MAX_IMAGE_SIDE_PX)
        self.assertGreater(max(width, height), MAX_IMAGE_SIDE_PX - 2)

    def test_process_rejects_oversized_file(self):
        """Garante rejeição de arquivo acima de 15 MB."""
        upload = SimpleUploadedFile(
            "huge.jpg",
            b"x" * (15 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            process_uploaded_image(upload)

    def test_process_rejects_invalid_content(self):
        """Garante rejeição de conteúdo que não é imagem."""
        upload = SimpleUploadedFile(
            "invalid.jpg",
            b"not-an-image",
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            process_uploaded_image(upload)

    def test_process_image_bytes_resizes_large_content(self):
        """Garante redimensionamento de bytes brutos como em cópia de logo."""
        buffer = BytesIO()
        Image.new("RGB", (1800, 900), color="navy").save(buffer, format="JPEG")
        content = buffer.getvalue()

        image_bytes, extension, width, height = process_image_bytes(
            content,
            filename="logo.jpg",
            content_type="image/jpeg",
        )

        self.assertGreater(len(image_bytes), 0)
        self.assertEqual(extension, "jpg")
        self.assertLessEqual(max(width, height), MAX_IMAGE_SIDE_PX)
        self.assertGreater(max(width, height), MAX_IMAGE_SIDE_PX - 2)
