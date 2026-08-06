"""
Testes da montagem incremental em duas fases do laudo pericial.
"""

from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_PROPERTY_SCENE
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_READY,
    bootstrap_state,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import ReportBlockType

User = get_user_model()


class ForensicIncrementalBuildPhaseTests(TestCase):
    """Testes da ordem cronológica analyze → build inicial → categoria → seção de local."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito para montagem incremental."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_phases",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Phases",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _complete_metadata(self) -> CaseMetadata:
        """Retorna metadados completos para montagem sem prompts pendentes."""
        return CaseMetadata(
            report_number="7",
            report_year=2026,
            exam_objective="Examinar local.",
            requesting_authority="Dr. Silva",
            police_district="1º DP",
            occurrence_report="BO-7",
            police_inquiry="IP-7",
            designation_date=date(2026, 1, 15),
            occurrence_at=datetime(2026, 1, 10, 14, 30),
            requisition_at=datetime(2026, 1, 11, 10, 0),
            attendance_protocol="PROT-7",
            examination_at=datetime(2026, 1, 16, 9, 0),
            photography="N/I",
            scanning_3d="N/I",
            sketch="N/I",
        )

    def _run_build_until_scene_prompt(self, report):
        """Executa passos incrementais até solicitar categoria de exame."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        state = bootstrap_state(report)
        while state not in (STATE_COLLECTING_SCENE_CONTINUATION, STATE_READY):
            _nodes, done, state, _step, _phase = advance_forensic_body_build_step(
                report,
                examiner=self.examiner,
            )
            report.refresh_from_db()
            if done and state == STATE_COLLECTING_SCENE_CONTINUATION:
                break

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_initial_build_opens_scene_continuation_before_category(self, mock_analyze):
        """Garante que montagem administrativa precede a pergunta de categoria de exame."""
        mock_analyze.return_value = (self._complete_metadata(), {}, {})
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse

        self.client.login(username="perito_phases", password="senha-segura")
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": SimpleUploadedFile("req.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )
        report.refresh_from_db()
        self._run_build_until_scene_prompt(report)

        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_SCENE_CONTINUATION)
        headings = list(
            report.nodes.order_by("position").values_list("block__content__text", flat=True)
        )
        self.assertIn("Objetivo do Exame", headings)
        self.assertNotIn("Descrição e Exame do Local", headings)

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content.generate_scene_examination_content"
    )
    def test_scene_section_is_inserted_before_closing_blocks(self, mock_generate):
        """Garante inserção mid-tree da seção de local antes do fechamento."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
            save_bootstrap_after_analyze,
        )

        save_bootstrap_after_analyze(report, self._complete_metadata(), field_coverage={})
        self._run_build_until_scene_prompt(report)

        from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Portão metálico.",
            location=SceneLocationData(kind="address", address="Rua Teste, 10"),
        )
        report.refresh_from_db()

        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        state = bootstrap_state(report)
        while state == STATE_BUILDING:
            advance_forensic_body_build_step(report, examiner=self.examiner)
            report.refresh_from_db()
            state = bootstrap_state(report)

        self.assertEqual(bootstrap_state(report), STATE_READY)
        texts = [
            node.block.content.get("text", "")
            for node in report.nodes.select_related("block").order_by("position")
        ]
        scene_index = next(i for i, text in enumerate(texts) if text == "Descrição e Exame do Local")
        closing_index = next(i for i, text in enumerate(texts) if "Nada mais havendo" in text)
        self.assertLess(scene_index, closing_index)
