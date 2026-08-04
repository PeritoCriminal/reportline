"""
Testes de merge entre metadados manuais e inferidos.
"""

from datetime import date

from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.metadata_merge import merge_case_metadata


class CaseMetadataMergeTests(TestCase):
    """Testes da prioridade de valores informados manualmente no intake."""

    def test_manual_values_override_inferred_fields(self):
        """Garante que campos preenchidos no formulário prevalecem sobre a IA."""
        manual = CaseMetadata(
            report_number="10",
            report_year=2026,
            requesting_authority="Dr. Manual",
            police_district="",
        )
        inferred = CaseMetadata(
            report_number="99",
            report_year=2025,
            requesting_authority="Dra. Inferida",
            police_district="Delegacia Inferida",
        )

        merged = merge_case_metadata(manual, inferred)

        self.assertEqual(merged.report_number, "10")
        self.assertEqual(merged.report_year, 2026)
        self.assertEqual(merged.requesting_authority, "Dr. Manual")
        self.assertEqual(merged.police_district, "Delegacia Inferida")

    def test_inferred_fills_empty_manual_fields(self):
        """Garante preenchimento inferido apenas para campos vazios."""
        manual = CaseMetadata(report_number="1", report_year=2026)
        inferred = CaseMetadata(
            report_number="2",
            report_year=2024,
            designation_date=date(2026, 1, 15),
            occurrence_report="BO-123",
        )

        merged = merge_case_metadata(manual, inferred)

        self.assertEqual(merged.designation_date, date(2026, 1, 15))
        self.assertEqual(merged.occurrence_report, "BO-123")
