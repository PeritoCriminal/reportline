# reportline/institution_ic_sp/tests/test_scene_location_dossier.py
"""
Testes de localização de exame inferida a partir do dossiê pericial.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_PROPERTY_SCENE
from institution_ic_sp.forensic_report.common.services.scene_location import (
    LOCATION_KIND_ADDRESS,
    SceneLocationData,
    exam_location_from_dossier,
    resolve_scene_location,
    scene_location_for_report,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import attach_bootstrap_meta
from institution_ic_sp.forensic_report.services.forensic_report_dossier import persist_initial_data_phase
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
    scene_characteristics_from_bootstrap,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class SceneLocationDossierFallbackTests(TestCase):
    """Testes de fallback de localização a partir de extensions do dossiê."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo pericial."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_scene_location",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Scene Location",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _mark_initial_build_completed(self, report):
        """Simula conclusão da montagem inicial para continuação de local."""
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["initial_build_completed"] = True
        bootstrap["scene_insert_after_node_id"] = "node-anchor"
        bootstrap["nodes"] = {"attendance_list": "node-anchor"}
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

    def test_exam_location_from_dossier_reads_confirmed_extensions(self):
        """Garante leitura de exam_location_address da fase initial_data."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["extensions"] = {"exam_location_address": "Rua do Dossiê, 200"}
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        persist_initial_data_phase(report, CaseMetadata(report_number="1", report_year=2026))

        location = exam_location_from_dossier(report)

        self.assertEqual(location.kind, LOCATION_KIND_ADDRESS)
        self.assertEqual(location.address, "Rua do Dossiê, 200")

    def test_resolve_scene_location_prefers_manual_over_dossier(self):
        """Garante prioridade do endereço informado pelo perito sobre o dossiê."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["extensions"] = {"exam_location_address": "Rua do Dossiê, 200"}
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])
        persist_initial_data_phase(report, CaseMetadata(report_number="2", report_year=2026))

        manual = SceneLocationData(kind=LOCATION_KIND_ADDRESS, address="Rua Manual, 10")
        resolved = resolve_scene_location(manual=manual, report=report)

        self.assertEqual(resolved.address, "Rua Manual, 10")

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content"
        ".generate_scene_examination_content"
    )
    def test_scene_continuation_uses_dossier_location_when_manual_absent(self, mock_generate):
        """Garante persistência do endereço do dossiê na continuação de exame de local."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Compareceu a equipe.",
            "characteristics_paragraph": "Casa térrea.",
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["extensions"] = {"exam_location_address": "Av. Central, 500"}
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])
        persist_initial_data_phase(report, CaseMetadata(report_number="3", report_year=2026))
        self._mark_initial_build_completed(report)

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Entrada lateral.",
            image_ids=[],
            location=SceneLocationData(),
        )
        report.refresh_from_db()

        characteristics = scene_characteristics_from_bootstrap(report.page_layout)
        self.assertEqual(
            characteristics["location"]["address"],
            "Av. Central, 500",
        )
        self.assertTrue(scene_location_for_report(report).is_present)
