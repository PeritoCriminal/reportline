"""Testes de limpeza de imagens do layout de página (cabeçalho e rodapé)."""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from reports.models import Report, ReportImage
from reports.services.report_image_upload import build_image_block_content, store_report_image
from reports.services.report_kind import attach_institutional_page_layout_snapshot, forensic_report_meta
from reports.services.report_page_layout import (
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    apply_header_template,
    clear_band_logo_cell,
    update_logo_cell_from_image,
)
from reports.services.report_page_layout_image_cleanup import (
    collect_image_ids_from_page_layout,
    delete_removed_page_layout_images,
)

User = get_user_model()


class ReportPageLayoutImageCleanupTests(TestCase):
    """Testes de remoção de ReportImage ao excluir ou substituir logos de página."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="layout_cleanup",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Layout cleanup")

    def _store_image(self, color: str = "red") -> ReportImage:
        """Cria imagem persistida vinculada ao relatório."""
        buffer = BytesIO()
        Image.new("RGB", (320, 200), color=color).save(buffer, format="JPEG")
        buffer.seek(0)
        upload = SimpleUploadedFile("logo.jpg", buffer.read(), content_type="image/jpeg")
        return store_report_image(self.report, upload)

    def _logo_cell_from_image(self, report_image: ReportImage) -> dict:
        """Monta célula de logo a partir de ReportImage."""
        content = build_image_block_content(report_image)
        return {
            "type": "logo",
            "logo_slot": "primary",
            "file": content["file"],
            "image_id": content["image_id"],
            "width": 120,
            "height": 80,
            "alt": "",
        }

    def test_collect_image_ids_from_page_layout(self):
        """Garante coleta de image_id das células de logo do layout."""
        image = self._store_image("green")
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout["header"]["cells"][0] = self._logo_cell_from_image(image)

        ids = collect_image_ids_from_page_layout(layout)

        self.assertEqual(ids, {str(image.pk)})

    def test_clear_logo_cell_removes_report_image_when_saved(self):
        """Garante remoção do arquivo ao esvaziar célula de logo do cabeçalho."""
        image = self._store_image("blue")
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout["header"]["cells"][0] = self._logo_cell_from_image(image)
        image_id = image.pk

        updated = clear_band_logo_cell(layout, band="header", cell_index=0)
        delete_removed_page_layout_images(layout, updated)

        self.assertEqual(updated["header"]["cells"][0]["image_id"], "")
        self.assertFalse(ReportImage.objects.filter(pk=image_id).exists())

    def test_replace_logo_cell_removes_previous_report_image(self):
        """Garante remoção da imagem anterior ao substituir logo do cabeçalho."""
        old_image = self._store_image("yellow")
        new_image = self._store_image("cyan")
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout["header"]["cells"][0] = self._logo_cell_from_image(old_image)
        old_image_id = old_image.pk

        new_payload = build_image_block_content(new_image)
        updated = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload=new_payload,
        )
        delete_removed_page_layout_images(layout, updated)

        self.assertEqual(updated["header"]["cells"][0]["image_id"], str(new_image.pk))
        self.assertFalse(ReportImage.objects.filter(pk=old_image_id).exists())
        self.assertTrue(ReportImage.objects.filter(pk=new_image.pk).exists())

    def test_snapshot_protected_logo_is_not_deleted_on_replace(self):
        """Garante que emblemas do snapshot institucional não sejam removidos ao trocar logo."""
        snapshot_image = self._store_image("green")
        new_image = self._store_image("cyan")
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout["header"]["cells"][0] = self._logo_cell_from_image(snapshot_image)
        layout.update(forensic_report_meta(workflow="generic"))
        layout = attach_institutional_page_layout_snapshot(layout)

        new_payload = build_image_block_content(new_image)
        updated = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload=new_payload,
        )
        delete_removed_page_layout_images(layout, updated)

        self.assertTrue(ReportImage.objects.filter(pk=snapshot_image.pk).exists())
        self.assertTrue(ReportImage.objects.filter(pk=new_image.pk).exists())
