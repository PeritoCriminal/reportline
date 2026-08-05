"""
Testes de restauração de cabeçalho e rodapé institucionais congelados.
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from io import BytesIO

from institution_ic_sp.forensic_report.services.institution_page_layout import (
    INSTITUTION_FOOTER_DISCLAIMER_LINE_1,
    INSTITUTION_HEADER_SECURITY_SECRETARIAT,
    build_institution_page_layout,
)
from institution_ic_sp.forensic_report.services.institutional_page_layout_restore import (
    restore_institutional_page_layout,
)
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import ReportImage
from reports.services.report_creation import create_report
from reports.services.report_kind import (
    INSTITUTIONAL_PAGE_LAYOUT_SNAPSHOT_KEY,
    institutional_page_layout_snapshot,
)

User = get_user_model()


class InstitutionalPageLayoutRestoreTests(TestCase):
    """Testes de snapshot e restauração de faixas institucionais."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo pericial com layout institucional."""
        from institution_ic_sp.models import ForensicTeam

        cls.institution = Institution.objects.get(acronym="IC-SP")
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.author = User.objects.create_user(
            username="perito_restore",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.author,
            forensic_team=cls.team,
            display_name="Dr. Restore",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _build_layout(self, report):
        """Monta layout institucional padrão para o laudo informado."""
        return build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=self.examiner,
            workflow="generic",
            main_title_text="LAUDO PERICIAL Nº 1/2026",
        )

    def test_build_institution_page_layout_stores_snapshot(self):
        """Garante cópia congelada de cabeçalho e rodapé na criação do laudo."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        layout = self._build_layout(report)

        snapshot = institutional_page_layout_snapshot(layout)
        self.assertIsNotNone(snapshot)
        self.assertIn(INSTITUTION_HEADER_SECURITY_SECRETARIAT, snapshot["header"]["cells"][1]["text"])
        self.assertIn(INSTITUTION_FOOTER_DISCLAIMER_LINE_1, snapshot["footer"]["cells"][0]["text"])
        self.assertIn(
            INSTITUTIONAL_PAGE_LAYOUT_SNAPSHOT_KEY,
            layout["reportline_meta"],
        )

    def _build_image_file(self, name: str = "logo.png") -> SimpleUploadedFile:
        """Gera arquivo PNG mínimo para logos institucionais."""
        buffer = BytesIO()
        Image.new("RGB", (120, 60), color="blue").save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile(name, buffer.read(), content_type="image/png")

    def test_build_institution_page_layout_copies_logos_to_report_images(self):
        """Garante que emblemas institucionais sejam gravados como imagens do laudo."""
        self.institution.sp_logo.save("sp.png", self._build_image_file("sp.png"), save=True)
        self.institution.sptc_logo.save("sptc.png", self._build_image_file("sptc.png"), save=True)

        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        layout = self._build_layout(report)

        image_ids = [
            cell.get("image_id")
            for cell in layout["header"]["cells"]
            if cell.get("type") == "logo" and cell.get("image_id")
        ]
        self.assertEqual(len(image_ids), 2)
        for image_id in image_ids:
            image = ReportImage.objects.get(pk=image_id)
            self.assertEqual(image.report_id, report.pk)
            self.assertTrue(image.image.name)

    def test_restore_institutional_page_layout_recovers_original_header(self):
        """Garante restauração do cabeçalho após edição manual."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        report.page_layout = self._build_layout(report)
        report.save(update_fields=["page_layout"])

        report.page_layout["header"]["cells"][1]["text"] = "Texto alterado pelo perito"
        report.save(update_fields=["page_layout"])

        restored = restore_institutional_page_layout(report, section="header")
        report.page_layout = restored
        report.save(update_fields=["page_layout"])
        report.refresh_from_db()

        self.assertIn(INSTITUTION_HEADER_SECURITY_SECRETARIAT, restored["header"]["cells"][1]["text"])
        self.assertNotIn("Texto alterado pelo perito", report.page_layout["header"]["cells"][1]["text"])

    def test_restore_institutional_page_layout_recovers_original_footer(self):
        """Garante restauração do rodapé após edição manual."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        report.page_layout = self._build_layout(report)
        report.save(update_fields=["page_layout"])

        report.page_layout["footer"]["cells"][0]["text"] = "Rodapé personalizado"
        report.save(update_fields=["page_layout"])

        restored = restore_institutional_page_layout(report, section="footer")
        report.page_layout = restored
        report.save(update_fields=["page_layout"])
        report.refresh_from_db()

        self.assertIn(INSTITUTION_FOOTER_DISCLAIMER_LINE_1, restored["footer"]["cells"][0]["text"])
        self.assertNotIn("Rodapé personalizado", report.page_layout["footer"]["cells"][0]["text"])

    def test_restore_institutional_header_rehydrates_logos_from_institution(self):
        """Garante recriação dos emblemas a partir da instituição quando removidos do laudo."""
        self.institution.sp_logo.save("sp.png", self._build_image_file("sp.png"), save=True)
        self.institution.sptc_logo.save("sptc.png", self._build_image_file("sptc.png"), save=True)

        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        report.page_layout = self._build_layout(report)
        report.save(update_fields=["page_layout"])

        snapshot_image_ids = [
            cell.get("image_id")
            for cell in report.page_layout["header"]["cells"]
            if cell.get("type") == "logo" and cell.get("image_id")
        ]
        ReportImage.objects.filter(pk__in=snapshot_image_ids).delete()

        restored = restore_institutional_page_layout(report, section="header")
        report.page_layout = restored
        report.save(update_fields=["page_layout"])

        restored_image_ids = [
            cell.get("image_id")
            for cell in restored["header"]["cells"]
            if cell.get("type") == "logo" and cell.get("image_id")
        ]
        self.assertEqual(len(restored_image_ids), 2)
        self.assertTrue(set(restored_image_ids).isdisjoint(set(snapshot_image_ids)))

        for image_id in restored_image_ids:
            image = ReportImage.objects.get(pk=image_id)
            self.assertEqual(image.report_id, report.pk)
            self.assertTrue(image.image.name)
