# reportline/institution_ic_sp/tests/test_forensic_bootstrap_field_coverage.py
"""
Testes de cobertura de campos inferidos pela IA no bootstrap pericial.
"""

from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.services.forensic_bootstrap import compute_pending_prompts
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    build_field_coverage_from_ai_payload,
    classify_datetime_raw,
    default_prompt_value,
    merge_field_coverage_with_metadata,
)


class ForensicBootstrapFieldCoverageTests(TestCase):
    """Testes de classificação de campos e defaults de prompts."""

    def test_classify_datetime_raw_detects_date_only(self):
        """Garante identificação de data sem hora no JSON da IA."""
        self.assertEqual(classify_datetime_raw("2026-03-15"), "date_only")
        self.assertEqual(classify_datetime_raw("2026-03-15T14:30"), "datetime")
        self.assertEqual(classify_datetime_raw(""), "missing")

    def test_pending_prompts_include_police_inquiry_when_missing(self):
        """Garante inquérito policial na fila quando a IA não identificou."""
        metadata = CaseMetadata(report_year=2026)
        pending = compute_pending_prompts(metadata)
        self.assertIn("police_inquiry", pending)

    def test_datetime_with_date_only_coverage_is_not_pending(self):
        """Garante ausência de prompt quando a IA identificou só a data."""
        metadata = CaseMetadata(
            report_year=2026,
            occurrence_at=timezone.make_aware(datetime(2026, 3, 15, 0, 0)),
        )
        coverage = {"occurrence_at": "date_only"}
        pending = compute_pending_prompts(metadata, field_coverage=coverage)
        self.assertNotIn("occurrence_at", pending)

    def test_default_prompt_value_uses_today_for_dates(self):
        """Garante preenchimento inicial com data atual em campos de data."""
        today = timezone.localdate().isoformat()
        self.assertEqual(default_prompt_value("designation_date"), today)
        self.assertTrue(default_prompt_value("occurrence_at").endswith("T00:00"))

    def test_build_field_coverage_marks_police_inquiry_from_payload(self):
        """Garante cobertura do inquérito policial a partir do JSON bruto."""
        coverage = build_field_coverage_from_ai_payload({"police_inquiry": "IP-1/2026"})
        self.assertEqual(coverage.get("police_inquiry"), "full")

    def test_merge_coverage_respects_existing_metadata(self):
        """Garante que metadados preenchidos marcam cobertura completa."""
        metadata = CaseMetadata(report_year=2026, police_inquiry="IP-2")
        merged = merge_field_coverage_with_metadata(metadata, {"police_inquiry": "missing"})
        self.assertEqual(merged["police_inquiry"], "full")
