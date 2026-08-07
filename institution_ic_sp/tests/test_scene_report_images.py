# reportline/institution_ic_sp/tests/test_scene_report_images.py
"""
Testes de legendas inferidas e inserção de imagens nativas na seção de local.
"""

from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_PROPERTY_SCENE
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_READY,
    bootstrap_state,
    save_bootstrap_after_analyze,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
)
from institution_ic_sp.forensic_report.workflows.property_crime.ai.services.scene_examination_inference import (
    _normalize_ai_content,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import ReportBlockType, ReportImage
from reports.services.report_image_attachments import ReportImageAttachment
from reports.services.report_image_upload import store_report_image

User = get_user_model()


class SceneReportImagesInferenceTests(TestCase):
    """Testes da normalização de legendas inferidas pela IA."""

    def test_normalize_report_images_only_for_show_in_report(self):
        """Garante legendas apenas para imagens marcadas para exibição no laudo."""
        attachments = [
            ReportImageAttachment(image_id="a", show_in_report=False, proposed_caption="Oculta"),
            ReportImageAttachment(image_id="b", show_in_report=True, proposed_caption="Proposta"),
        ]
        payload = {
            "report_images": [
                {"image_id": "a", "caption": "Não deve entrar"},
                {"image_id": "b", "caption": "Legenda final"},
            ]
        }

        result = _normalize_ai_content(payload, attachments=attachments)

        self.assertEqual(result["report_images"], [{"image_id": "b", "caption": "Legenda final"}])

    def test_normalize_report_images_falls_back_to_proposed_caption(self):
        """Garante fallback para legenda proposta quando a IA não devolve texto."""
        attachments = [
            ReportImageAttachment(image_id="b", show_in_report=True, proposed_caption="Portão metálico"),
        ]

        result = _normalize_ai_content({"report_images": []}, attachments=attachments)

        self.assertEqual(result["report_images"][0]["caption"], "Portão metálico")

    def test_normalize_report_images_strips_figure_prefix(self):
        """Garante remoção de prefixo Figura N inferido pela IA."""
        attachments = [
            ReportImageAttachment(image_id="b", show_in_report=True, proposed_caption=""),
        ]
        payload = {
            "report_images": [
                {"image_id": "b", "caption": "Figura 4 - Vista frontal do imóvel."},
            ]
        }

        result = _normalize_ai_content(payload, attachments=attachments)

        self.assertEqual(result["report_images"][0]["caption"], "Vista frontal do imóvel.")

    def test_normalize_report_image_attachments_strips_figure_prefix(self):
        """Garante remoção de prefixo Figura N em legenda proposta do upload."""
        from reports.services.report_image_attachments import normalize_report_image_attachments

        attachments = normalize_report_image_attachments(
            [{"image_id": "abc", "show_in_report": True, "proposed_caption": "Figura 2 - Portão."}]
        )

        self.assertEqual(attachments[0].proposed_caption, "Portão.")


class SceneReportImagesBuildTests(TestCase):
    """Testes da inserção de blocos IMAGE e legenda após os parágrafos de local."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo para montagem incremental."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_scene_images",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Scene Images",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _complete_metadata(self) -> CaseMetadata:
        """Retorna metadados completos para montagem sem prompts pendentes."""
        return CaseMetadata(
            report_number="8",
            report_year=2026,
            exam_objective="Examinar local.",
            requesting_authority="Dr. Silva",
            police_district="1º DP",
            occurrence_report="BO-8",
            police_inquiry="IP-8",
            designation_date=date(2026, 1, 15),
            occurrence_at=datetime(2026, 1, 10, 14, 30),
            requisition_at=datetime(2026, 1, 11, 10, 0),
            attendance_protocol="PROT-8",
            examination_at=datetime(2026, 1, 16, 9, 0),
            photography="N/I",
            scanning_3d="N/I",
            sketch="N/I",
        )

    def _mark_initial_build_completed(self, report):
        """Simula conclusão da montagem inicial."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        state = bootstrap_state(report)
        while state not in (STATE_COLLECTING_SCENE_CONTINUATION, STATE_READY):
            advance_forensic_body_build_step(report, examiner=self.examiner)
            report.refresh_from_db()
            state = bootstrap_state(report)

    def _store_test_image(self, report) -> ReportImage:
        """Persiste imagem JPEG mínima vinculada ao laudo."""
        buffer = BytesIO()
        Image.new("RGB", (40, 30), color="red").save(buffer, format="JPEG")
        buffer.seek(0)
        uploaded = SimpleUploadedFile("fachada.jpg", buffer.read(), content_type="image/jpeg")
        return store_report_image(report, uploaded)

    def _run_build_until_scene_prompt(self, report):
        """Executa passos incrementais até solicitar categoria de exame."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        state = bootstrap_state(report)
        while state not in (STATE_COLLECTING_SCENE_CONTINUATION, STATE_READY):
            advance_forensic_body_build_step(report, examiner=self.examiner)
            report.refresh_from_db()
            state = bootstrap_state(report)

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content.generate_scene_examination_content"
    )
    def test_scene_build_inserts_image_and_caption_nodes(self, mock_generate):
        """Garante inserção de blocos nativos IMAGE e parágrafo legenda após características."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
            "report_images": [],
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        save_bootstrap_after_analyze(report, self._complete_metadata(), field_coverage={})
        self._run_build_until_scene_prompt(report)

        report_image = self._store_test_image(report)
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
            "report_images": [
                {
                    "image_id": str(report_image.pk),
                    "caption": "Vista frontal do imóvel.",
                }
            ],
        }

        from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Fachada com portão.",
            images=[
                ReportImageAttachment(
                    image_id=str(report_image.pk),
                    show_in_report=True,
                    proposed_caption="Fachada",
                )
            ],
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

        nodes = list(report.nodes.select_related("block").order_by("position"))
        image_nodes = [node for node in nodes if node.block.block_type == ReportBlockType.IMAGE]
        self.assertEqual(len(image_nodes), 1)
        self.assertEqual(image_nodes[0].block.content.get("image_id"), str(report_image.pk))

        image_index = nodes.index(image_nodes[0])
        caption_node = nodes[image_index + 1]
        self.assertEqual(caption_node.block.block_type, ReportBlockType.PARAGRAPH)
        self.assertEqual(caption_node.block.content.get("text"), "Vista frontal do imóvel.")

        characteristics_index = next(
            i
            for i, node in enumerate(nodes)
            if node.block.content.get("text") == "Imóvel residencial."
        )
        self.assertLess(characteristics_index, image_index)
