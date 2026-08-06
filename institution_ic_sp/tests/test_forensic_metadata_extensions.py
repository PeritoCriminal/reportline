"""
Testes de normalização e persistência de ``extensions`` na extração administrativa.
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.ai.prompt_loader import load_case_metadata_schema_summary
from institution_ic_sp.forensic_report.common.ai.structured_output import extensions_from_ai_payload
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    analyze_case_metadata_with_coverage,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    extensions_from_bootstrap,
    save_bootstrap_after_analyze,
)
from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
    initial_data_phase_from_dossier,
    persist_initial_data_phase,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from django.contrib.auth import get_user_model

User = get_user_model()


class MetadataExtensionsParsingTests(TestCase):
    """Testes da extração e normalização do objeto extensions."""

    def test_extensions_from_ai_payload_normalizes_keys_and_values(self):
        """Garante normalização de chaves e valores serializáveis em extensions."""
        payload = {
            "report_number": "1",
            "extensions": {
                " exam_location_address ": "Rua A, 10",
                "victim_names": ["Maria", "", None],
                "empty_value": "",
                "nested": {"vehicle_plates": "ABC1D23"},
            },
        }

        extensions = extensions_from_ai_payload(payload)

        self.assertEqual(extensions["exam_location_address"], "Rua A, 10")
        self.assertEqual(extensions["victim_names"], ["Maria"])
        self.assertEqual(extensions["nested"]["vehicle_plates"], "ABC1D23")
        self.assertNotIn("empty_value", extensions)

    def test_schema_summary_includes_extensions(self):
        """Garante que o resumo do schema oriente a IA sobre extensions."""
        summary = load_case_metadata_schema_summary()

        self.assertIn("extensions", summary)
        self.assertIn("snake_case", summary.lower())


class MetadataExtensionsPersistenceTests(TestCase):
    """Testes de persistência de extensions no bootstrap e dossiê."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito para fluxo de laudo pericial."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_extensions",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Extensions",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_save_bootstrap_after_analyze_persists_extensions(self):
        """Garante gravação de extensions no bootstrap após análise documental."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        metadata = CaseMetadata(report_number="10", report_year=2026)
        extensions = {"exam_location_address": "Rua Central, 50"}

        save_bootstrap_after_analyze(
            report,
            metadata,
            field_coverage={},
            document_count=2,
            extensions=extensions,
        )
        report.refresh_from_db()

        self.assertEqual(
            extensions_from_bootstrap(report.page_layout),
            {"exam_location_address": "Rua Central, 50"},
        )

    def test_initial_data_phase_persists_extensions_in_dossier(self):
        """Garante cópia de extensions do bootstrap para o dossiê na fase initial_data."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["extensions"] = {
            "exam_location_address": "Av. Paulista, 1000",
            "witness_names": "João Silva",
        }
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        metadata = CaseMetadata(report_number="11", report_year=2026)
        persist_initial_data_phase(report, metadata)

        phase = initial_data_phase_from_dossier(report)
        self.assertEqual(phase["data"]["extensions"]["exam_location_address"], "Av. Paulista, 1000")
        self.assertEqual(phase["data"]["extensions"]["witness_names"], "João Silva")

    def test_analyze_case_metadata_with_coverage_returns_extensions(self):
        """Garante retorno de extensions junto com metadados e cobertura."""
        from unittest.mock import patch

        payload = {
            "report_number": "7",
            "extensions": {"occurrence_address": "Rua B, 20"},
        }
        with patch(
            "institution_ic_sp.forensic_report.common.services.case_metadata_extraction"
            ".infer_case_metadata_ai_payload",
            return_value=payload,
        ):
            merged, coverage, extensions = analyze_case_metadata_with_coverage(
                manual=CaseMetadata(),
                uploaded_files=None,
            )

        self.assertEqual(merged.report_number, "7")
        self.assertIsInstance(coverage, dict)
        self.assertEqual(extensions["occurrence_address"], "Rua B, 20")
