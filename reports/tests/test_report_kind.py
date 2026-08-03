"""
Testes do serviço de identificação de laudos periciais.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportStatus
from reports.services.report_kind import (
    FORENSIC_REPORT_KIND,
    REPORTLINE_META_KEY,
    forensic_report_meta,
    is_forensic_report,
)
from reports.services.report_page_layout import default_page_layout, normalize_page_layout

User = get_user_model()


class ReportKindServiceTests(TestCase):
    """Testes de metadados de laudo pericial em page_layout."""

    @classmethod
    def setUpTestData(cls):
        """Prepara autor e relatório base."""
        cls.author = User.objects.create_user(
            username="perito_kind",
            password="senha-segura",
        )

    def test_is_forensic_report_detects_marker(self):
        """Garante identificação de laudo pericial pelo marcador em page_layout."""
        layout = default_page_layout()
        layout.update(forensic_report_meta(workflow="generic"))
        report = Report.objects.create(
            author=self.author,
            title="Laudo pericial 1/2026",
            status=ReportStatus.DRAFT,
            page_layout=layout,
        )

        self.assertTrue(is_forensic_report(report))

    def test_regular_report_is_not_forensic(self):
        """Garante que relatório comum não é classificado como laudo pericial."""
        report = Report.objects.create(
            author=self.author,
            title="Relatório comum",
            status=ReportStatus.DRAFT,
            page_layout=default_page_layout(),
        )

        self.assertFalse(is_forensic_report(report))

    def test_normalize_page_layout_preserves_reportline_meta(self):
        """Garante que normalização de layout preserve metadados do ReportLine."""
        payload = default_page_layout()
        payload[REPORTLINE_META_KEY] = {
            "kind": FORENSIC_REPORT_KIND,
            "workflow": "generic",
        }

        normalized = normalize_page_layout(payload)

        self.assertEqual(
            normalized[REPORTLINE_META_KEY]["kind"],
            FORENSIC_REPORT_KIND,
        )
