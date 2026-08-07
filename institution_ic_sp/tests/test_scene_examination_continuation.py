# reportline/institution_ic_sp/tests/test_scene_examination_continuation.py
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
from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_ANALYZED,
    STATE_BUILDING,
    STATE_COLLECTING_PROMPTS,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_READY,
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


class SceneExaminationContentGenerationTests(TestCase):
    """Testes da geração de conteúdo da seção de exame de local."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo para geração de conteúdo."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_scene_content",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Scene Content",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content"
        ".infer_scene_examination_content"
    )
    def test_generate_scene_examination_content_resolves_location(self, mock_infer):
        """Garante resolução de localização ao gerar parágrafos do exame de local."""
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
            attach_bootstrap_meta,
            empty_bootstrap_payload,
        )
        from institution_ic_sp.forensic_report.services.scene_examination_content import (
            generate_scene_examination_content,
        )

        mock_infer.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "A equipe compareceu ao local.",
            "characteristics_paragraph": "Imóvel residencial térreo.",
        }
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        bootstrap = empty_bootstrap_payload()
        bootstrap["metadata"] = {
            "exam_objective": "Examinar local de furto.",
            "exam_category": EXAM_CATEGORY_PROPERTY_SCENE,
        }
        bootstrap["scene_characteristics"] = {
            "prompt": "Portão basculante.",
            "image_ids": [],
            "location": {
                "kind": "address",
                "address": "Rua das Flores, 100",
                "latitude": "",
                "longitude": "",
            },
        }
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        content = generate_scene_examination_content(report)

        self.assertEqual(content["characteristics_heading"], "Características do Local")
        mock_infer.assert_called_once()
        location = mock_infer.call_args.kwargs["location"]
        self.assertTrue(location.is_present)
        self.assertEqual(location.address, "Rua das Flores, 100")


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

    def _mark_initial_build_completed(self, report):
        """Simula conclusão da montagem inicial para testes de continuação."""
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
            STATE_COLLECTING_SCENE_CONTINUATION,
            attach_bootstrap_meta,
            get_bootstrap_meta,
        )
        from institution_ic_sp.forensic_report.services.forensic_report_body_builder import (
            _create_report_node,
        )
        from reports.models import ReportBlockType

        attendance = _create_report_node(
            report,
            position=1,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Atendimento"},
        )
        _create_report_node(
            report,
            position=2,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": ""},
        )

        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        bootstrap["initial_build_completed"] = True
        bootstrap["nodes"] = {
            "attendance_list": str(attendance.pk),
            "body_spacer": str(attendance.pk),
        }
        bootstrap["scene_insert_after_node_id"] = str(attendance.pk)
        bootstrap["state"] = STATE_COLLECTING_SCENE_CONTINUATION
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])
        return report

    def test_analyze_transitions_to_collecting_prompts_when_fields_missing(self):
        """Garante que análise documental abre prompts antes da montagem inicial."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = CaseMetadata(exam_objective="Examinar local de furto.")

        save_bootstrap_after_analyze(report, metadata, field_coverage={})
        report.refresh_from_db()

        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_PROMPTS)
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

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content"
        ".generate_scene_examination_content"
    )
    def test_scene_continuation_property_scene_persists_characteristics(self, mock_generate):
        """Garante persistência de prompt e imagens para exame de local patrimonial."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "A equipe compareceu ao local.",
            "characteristics_paragraph": "Imóvel residencial térreo.",
        }
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = self._complete_metadata()
        save_bootstrap_after_analyze(report, metadata, field_coverage={})
        self._mark_initial_build_completed(report)

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Portão basculante e sala de estar.",
            image_ids=["img-1", "img-2"],
            location=SceneLocationData(
                kind="address",
                address="Rua das Flores, 100",
            ),
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
        self.assertEqual(
            bootstrap["scene_characteristics"]["location"]["address"],
            "Rua das Flores, 100",
        )
        self.assertIn("scene_examination_content", bootstrap)
        self.assertEqual(bootstrap_state(report), STATE_BUILDING)

    def test_scene_continuation_deferred_module_advances_without_characteristics(self):
        """Garante avanço com TODO implícito para módulos ainda não desenvolvidos."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        metadata = replace(self._complete_metadata(), exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT)
        save_bootstrap_after_analyze(report, metadata, field_coverage={})
        self._mark_initial_build_completed(report)

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        )
        report.refresh_from_db()

        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        self.assertTrue(bootstrap["scene_continuation_completed"])
        self.assertEqual(bootstrap["exam_category"], EXAM_CATEGORY_TRAFFIC_ACCIDENT)
        self.assertNotIn("scene_characteristics", bootstrap)
        self.assertEqual(bootstrap_state(report), STATE_READY)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_rejects_invalid_category(self, mock_analyze):
        """Garante validação de categoria inválida no endpoint de continuação."""
        mock_analyze.return_value = (CaseMetadata(exam_objective="Examinar local."), {}, {})
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )
        report.refresh_from_db()
        self._mark_initial_build_completed(report)

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
    def test_scene_continuation_endpoint_rejects_images_without_permission(self, mock_analyze):
        """Garante 403 quando perito envia imagens sem permissão institucional."""
        mock_analyze.return_value = (self._complete_metadata(), {}, {})
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )
        report.refresh_from_db()
        self._mark_initial_build_completed(report)

        response = self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk}),
            data=json.dumps(
                {
                    "exam_category": EXAM_CATEGORY_PROPERTY_SCENE,
                    "prompt": "Portão metálico.",
                    "image_ids": ["img-1"],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("não está autorizado a enviar imagens", response.json()["errors"][0])

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content"
        ".generate_scene_examination_content"
    )
    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_advances_bootstrap(self, mock_analyze, mock_generate):
        """Garante que endpoint conclui continuação e retorna montagem da seção de local."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Compareceu a equipe.",
            "characteristics_paragraph": "Casa térrea.",
        }
        mock_analyze.return_value = (self._complete_metadata(), {}, {})
        self.client.login(username="perito_scene", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        self.client.post(
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
            {"documents": self._pdf_upload()},
        )
        report.refresh_from_db()
        self._mark_initial_build_completed(report)

        response = self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk}),
            data=json.dumps(
                {
                    "exam_category": EXAM_CATEGORY_PROPERTY_SCENE,
                    "prompt": "Fachada com portão metálico.",
                    "image_ids": [],
                    "location": {
                        "kind": "address",
                        "address": "Rua Teste, 10",
                    },
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], STATE_BUILDING)
        self.assertEqual(payload["exam_category"], EXAM_CATEGORY_PROPERTY_SCENE)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_BUILDING)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
        ".analyze_case_metadata_with_coverage"
    )
    def test_scene_continuation_endpoint_returns_todo_for_deferred_module(self, mock_analyze):
        """Garante mensagem TODO para acidente de trânsito ainda não implementado."""
        mock_analyze.return_value = (
            replace(self._complete_metadata(), exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT),
            {},
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
        report.refresh_from_db()
        self._mark_initial_build_completed(report)

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
