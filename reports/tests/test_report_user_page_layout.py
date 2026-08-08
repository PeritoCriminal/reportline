# reportline/reports/tests/test_report_user_page_layout.py
"""Testes de cabeçalho e rodapé padrão por usuário."""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from reports.models import Report, ReportImage, ReportUserConfig
from reports.services.report_creation import create_report
from reports.services.report_image_upload import store_report_image
from reports.services.report_kind import forensic_report_meta
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    apply_footer_template,
    apply_header_template,
    update_logo_cell_from_image,
)
from reports.services.report_user_config import get_or_create_user_config
from reports.services.report_user_page_layout import (
    apply_user_page_layout_to_report,
    clone_page_layout_for_report,
    merge_institutional_layout_with_user_preferences,
    sync_user_page_layout_preferences,
)

User = get_user_model()


class ReportUserPageLayoutTests(TestCase):
    """Testes de persistência e reaplicação de faixas de página por usuário."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="page_layout_user",
            password="senha-segura",
        )

    def _build_image_file(self) -> SimpleUploadedFile:
        buffer = BytesIO()
        Image.new("RGB", (400, 200), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile("logo.jpg", buffer.read(), content_type="image/jpeg")

    def test_sync_user_page_layout_preferences_stores_personal_bands(self):
        """Garante cópia de cabeçalho e rodapé pessoais para preferências do usuário."""
        report = Report.objects.create(author=self.author, title="Origem")
        layout = apply_header_template(report.page_layout, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout = apply_footer_template(layout, FOOTER_TEMPLATE_TEXT_ONLY)
        layout["header"]["cells"][1]["text"] = "Instituto de Criminalística"
        layout["footer"]["cells"][0]["text"] = "Página"

        sync_user_page_layout_preferences(self.author, layout)

        user_config = ReportUserConfig.objects.get(user=self.author)
        self.assertTrue(user_config.personal_page_layout["header"]["enabled"])
        self.assertTrue(user_config.personal_page_layout["footer"]["enabled"])
        self.assertEqual(
            user_config.personal_page_layout["header"]["cells"][1]["text"],
            "Instituto de Criminalística",
        )
        self.assertEqual(
            user_config.personal_page_layout["footer"]["cells"][0]["text"],
            "Página",
        )

    def test_sync_user_page_layout_stores_forensic_in_institutional_bucket(self):
        """Garante que laudos periciais atualizem preferências institucionais."""
        user_config = get_or_create_user_config(self.author)
        user_config.personal_page_layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        user_config.personal_page_layout["footer"]["cells"][0]["text"] = "Rodapé pessoal"
        user_config.save()

        layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        layout.update(forensic_report_meta(workflow="generic"))
        layout["footer"]["cells"][0]["text"] = "Rodapé pericial"

        sync_user_page_layout_preferences(self.author, layout)

        user_config.refresh_from_db()
        self.assertEqual(
            user_config.personal_page_layout["footer"]["cells"][0]["text"],
            "Rodapé pessoal",
        )
        self.assertEqual(
            user_config.institutional_page_layout["footer"]["cells"][0]["text"],
            "Rodapé pericial",
        )

    def test_create_report_applies_saved_personal_page_layout(self):
        """Garante que laudo pessoal novo recebe último cabeçalho e rodapé do usuário."""
        user_config = get_or_create_user_config(self.author)
        user_config.personal_page_layout = apply_footer_template(
            apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT),
            FOOTER_TEMPLATE_TEXT_ONLY,
        )
        user_config.personal_page_layout["header"]["cells"][1]["text"] = "IC-SP"
        user_config.save()

        report = create_report(author=self.author, title="Novo laudo")

        self.assertTrue(report.page_layout["header"]["enabled"])
        self.assertTrue(report.page_layout["footer"]["enabled"])
        self.assertEqual(report.page_layout["header"]["cells"][1]["text"], "IC-SP")

    def test_merge_institutional_layout_with_user_preferences_preserves_snapshot(self):
        """Garante aplicação de preferências institucionais sem alterar snapshot oficial."""
        user_config = get_or_create_user_config(self.author)
        user_config.institutional_page_layout = apply_footer_template(
            apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT),
            FOOTER_TEMPLATE_TEXT_ONLY,
        )
        user_config.institutional_page_layout["header"]["cells"][1]["text"] = "Cabeçalho salvo"
        user_config.save()

        report = Report.objects.create(author=self.author, title="Laudo pericial")
        fresh_layout = apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        fresh_layout.update(forensic_report_meta(workflow="generic"))
        fresh_layout["header"]["cells"][1]["text"] = "Cabeçalho oficial"
        fresh_layout["reportline_meta"]["institutional_page_layout_snapshot"] = {
            "header": fresh_layout["header"],
            "footer": fresh_layout["footer"],
        }

        merged = merge_institutional_layout_with_user_preferences(
            report,
            self.author,
            fresh_layout,
        )

        self.assertEqual(merged["header"]["cells"][1]["text"], "Cabeçalho salvo")
        self.assertEqual(
            merged["reportline_meta"]["institutional_page_layout_snapshot"]["header"]["cells"][1]["text"],
            "Cabeçalho oficial",
        )

    def test_merge_institutional_layout_preserves_fresh_logos_when_prefs_empty(self):
        """Garante que preferências sem emblemas não apaguem logos do layout fresco."""
        user_config = get_or_create_user_config(self.author)
        user_config.institutional_page_layout = apply_footer_template(
            apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT),
            FOOTER_TEMPLATE_TEXT_ONLY,
        )
        user_config.institutional_page_layout["header"]["cells"][1]["text"] = "Cabeçalho salvo"
        user_config.save()

        report = Report.objects.create(author=self.author, title="Laudo pericial")
        source_image = store_report_image(report, self._build_image_file())
        fresh_layout = apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        fresh_layout.update(forensic_report_meta(workflow="generic"))
        fresh_layout = update_logo_cell_from_image(
            fresh_layout,
            cell_index=0,
            image_payload={
                "file": source_image.image.name,
                "image_id": str(source_image.pk),
                "width": 120,
                "height": 60,
                "alt": "Logo SP",
            },
        )
        fresh_layout["header"]["cells"][1]["text"] = "Cabeçalho oficial"
        fresh_layout["reportline_meta"]["institutional_page_layout_snapshot"] = {
            "header": fresh_layout["header"],
            "footer": fresh_layout["footer"],
        }

        merged = merge_institutional_layout_with_user_preferences(
            report,
            self.author,
            fresh_layout,
        )

        self.assertEqual(merged["header"]["cells"][1]["text"], "Cabeçalho salvo")
        self.assertEqual(merged["header"]["cells"][0]["image_id"], str(source_image.pk))
        self.assertEqual(merged["header"]["cells"][0]["file"], source_image.image.name)

    def test_clone_page_layout_for_report_duplicates_logo_images(self):
        """Garante clonagem de imagens de logo ao aplicar layout em laudo novo."""
        source_report = Report.objects.create(author=self.author, title="Origem")
        source_image = store_report_image(source_report, self._build_image_file())
        layout = apply_header_template(source_report.page_layout, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": source_image.image.name,
                "image_id": str(source_image.pk),
                "width": 120,
                "height": 60,
                "alt": "",
            },
        )

        target_report = Report.objects.create(author=self.author, title="Destino")
        cloned_layout = clone_page_layout_for_report(layout, target_report)

        cloned_image_id = cloned_layout["header"]["cells"][0]["image_id"]
        self.assertNotEqual(cloned_image_id, str(source_image.pk))
        cloned_image = ReportImage.objects.get(pk=cloned_image_id)
        self.assertEqual(cloned_image.report_id, target_report.pk)
        self.assertTrue(cloned_image.image.name)

    def test_apply_user_page_layout_to_report_uses_personal_preferences(self):
        """Garante serviço de aplicação direta das preferências pessoais no laudo."""
        user_config = get_or_create_user_config(self.author)
        user_config.personal_page_layout = apply_footer_template({}, FOOTER_TEMPLATE_TEXT_ONLY)
        user_config.personal_page_layout["footer"]["cells"][0]["text"] = "Rodapé padrão"
        user_config.save()

        report = Report.objects.create(author=self.author, title="Sem layout")
        apply_user_page_layout_to_report(report, self.author)

        report.refresh_from_db()
        self.assertTrue(report.page_layout["footer"]["enabled"])
        self.assertEqual(report.page_layout["footer"]["cells"][0]["text"], "Rodapé padrão")
