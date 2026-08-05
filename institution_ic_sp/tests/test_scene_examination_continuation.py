"""
Testes da continuação de exame de local no bootstrap pericial.
"""

import json
from dataclasses import replace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_PROPERTY_SCENE,
    EXAM_CATEGORY_TRAFFIC_ACCIDENT,
    EXAM_CATEGORY_UNKNOWN,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_ANALYZED,
    STATE_COLLECTING_PROMPTS,
    STATE_COLLECTING_SCENE_CONTINUATION,
    bootstrap_state,
    is_scene_continuation_completed,
    save_bootstrap_after_analyze,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class ExamCategoryNormalizationTests(TestCase):
    """Testes de normalização da categoria de exame pericial."""

    def test_unknown_values_fallback_to_unknown(self):
        """Garante fallback para unknown em valores inválidos ou vazios."""
        from institution_ic_sp.forensic_report.common.services.exam_category import (
            normalize_exam_category,
        )

        self.assertEqual(normalize_exam_category(""), EXAM_CATEGORY_UNKNOWN)
        self.assertEqual(normalize_exam_category("invalid"), EXAM_CATEGORY_UNKNOWN)

    def test_property_scene_is_recognized(self):
        """Garante reconhecimento da categoria de local patrimonial."""
        from institution_ic_sp.forensic_report.common.services.exam_category import (
            is_property_scene_category,
            normalize_exam_category,
        )

        self.assertEqual(normalize_exam_category("property_scene"), EXAM_CATEGORY_PROPERTY_SCENE)
        self.assertTrue(is_property_scene_category("property_scene"))


class SceneExaminationContinuationTests(TestCase):
    """Testes da etapa de continuação de exame de local no bootstrap."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo pericial em bootstrap."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_scene",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Scene",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_analyze_transitions_to_scene_continuation_state(self):
        """Garante que análise documental abre continuação de exame de local."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = CaseMetadata(exam_objective="Examinar local de furto.")

        save_bootstrap_after_analyze(report, metadata, field_coverage={})
        report.refresh_from_db()

        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_SCENE_CONTINUATION)
        self.assertFalse(is_scene_continuation_completed(report.page_layout))

    def _complete_metadata(self) -> CaseMetadata:
        """Retorna metadados completos para avançar direto ao estado analyzed."""
        from datetime import date, datetime

        return CaseMetadata(
            report_number="1",
            report_year=2026,
            exam_objective="Examinar local de furto.",
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            requesting_authority="Dr. Silva",
            police_district="1º DP",
            occurrence_report="BO-1",
            police_inquiry="IP-1",
            designation_date=date(2026, 1, 15),
            occurrence_at=datetime(2026, 1, 10, 14, 30),
            requisition_at=datetime(2026, 1, 11, 10, 0),
            attendance_protocol="PROT-1",
            examination_at=datetime(2026, 1, 16, 9, 0),
            photography="N/I",
            scanning_3d="N/I",
            sketch="N/I",
        )

    def test_scene_continuation_property_scene_persists_characteristics(self):
        """Garante persistência de prompt e imagens para exame de local patrimonial."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = self._complete_metadata()
        save_bootstrap_after_analyze(report, metadata, field_coverage={})

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Portão basculante e sala de estar.",
            image_ids=["img-1", "img-2"],
        )
        report.refresh_from_db()

        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        self.assertTrue(bootstrap["scene_continuation_completed"])
        self.assertEqual(bootstrap["exam_category"], EXAM_CATEGORY_PROPERTY_SCENE)
        self.assertEqual(
            bootstrap["scene_characteristics"]["prompt"],
            "Portão basculante e sala de estar.",
        )
        self.assertEqual(bootstrap["scene_characteristics"]["image_ids"], ["img-1", "img-2"])
        self.assertEqual(bootstrap_state(report), STATE_ANALYZED)

    def test_scene_continuation_deferred_module_advances_without_characteristics(self):
        """Garante avanço com TODO implícito para módulos ainda não desenvolvidos."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = replace(self._complete_metadata(), exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT)
        save_bootstrap_after_analyze(report, metadata, field_coverage={})

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        )
        report.refresh_from_db()

        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        self.assertTrue(bootstrap["scene_continuation_completed"])
        self.assertEqual(bootstrap["exam_category"], EXAM_CATEGORY_TRAFFIC_ACCIDENT)
        self.assertNotIn("scene_characteristics", bootstrap)
        self.assertEqual(bootstrap_state(report), STATE_ANALYZED)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_rejects_invalid_category(self, mock_analyze):
        """Garante validação de categoria inválida no endpoint de continuação."""
        mock_analyze.return_value = (CaseMetadata(exam_objective="Examinar local."), {})
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )

        response = self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk}),
            data=json.dumps({"exam_category": "invalid"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Categoria de exame inválida", response.json()["errors"][0])

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_advances_bootstrap(self, mock_analyze):
        """Garante que endpoint conclui continuação e retorna estado analisado."""
        mock_analyze.return_value = (self._complete_metadata(), {})
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )

        response = self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk}),
            data=json.dumps(
                {
                    "exam_category": EXAM_CATEGORY_PROPERTY_SCENE,
                    "prompt": "Fachada com portão metálico.",
                    "image_ids": [],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], STATE_ANALYZED)
        self.assertEqual(payload["exam_category"], EXAM_CATEGORY_PROPERTY_SCENE)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_ANALYZED)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_returns_todo_for_deferred_module(self, mock_analyze):
        """Garante mensagem TODO para acidente de trânsito ainda não implementado."""
        mock_analyze.return_value = (
            replace(self._complete_metadata(), exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT),
            {},
        )
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )

        response = self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk}),
            data=json.dumps({"exam_category": EXAM_CATEGORY_TRAFFIC_ACCIDENT}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("todo_message", response.json())

    def _pdf_upload(self):
        """Retorna PDF mínimo para upload em memória."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 scene continuation test",
            content_type="application/pdf",
        )
