# reportline/institution_ic_sp/tests/test_trace_observation_continuation.py
"""
Testes da coleta de vestígios (Elementos Observados) no bootstrap pericial.
"""

from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_PROPERTY_SCENE
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    STATE_COLLECTING_COLLECTED_ITEMS,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_COLLECTING_TRACES,
    bootstrap_state,
    get_bootstrap_meta,
    save_bootstrap_after_analyze,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
)
from institution_ic_sp.forensic_report.services.trace_observation_continuation import (
    TRACES_SECTION_HEADING,
    complete_traces_collection,
    save_trace_observation,
)
from institution_ic_sp.forensic_report.workflows.property_crime.ai.services.trace_observation_inference import (
    _normalize_ai_content,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import ReportBlockType, ReportImage
from reports.services.report_image_attachments import ReportImageAttachment
from reports.services.report_image_upload import store_report_image

User = get_user_model()


class TraceObservationInferenceTests(TestCase):
    """Testes da normalização de conteúdo inferido para vestígios."""

    def test_normalize_report_images_only_for_show_in_report(self):
        """Garante legendas apenas para imagens marcadas para exibição no laudo."""
        attachments = [
            ReportImageAttachment(image_id="a", show_in_report=False, proposed_caption="Oculta"),
            ReportImageAttachment(image_id="b", show_in_report=True, proposed_caption="Proposta"),
        ]
        payload = {
            "trace_paragraph": "Marca identificada na porta.",
            "report_images": [
                {"image_id": "a", "caption": "Não deve entrar"},
                {"image_id": "b", "caption": "Legenda final"},
            ],
        }

        result = _normalize_ai_content(payload, attachments=attachments)

        self.assertEqual(result["report_images"], [{"image_id": "b", "caption": "Legenda final"}])

    def test_normalize_report_images_strips_figure_prefix(self):
        """Garante remoção de prefixo Figura N inferido pela IA."""
        attachments = [
            ReportImageAttachment(image_id="b", show_in_report=True, proposed_caption=""),
        ]
        payload = {
            "trace_paragraph": "Marca identificada na porta.",
            "report_images": [
                {"image_id": "b", "caption": "Figura 3 - Detalhe da marca na fechadura."},
            ],
        }

        result = _normalize_ai_content(payload, attachments=attachments)

        self.assertEqual(result["report_images"][0]["caption"], "Detalhe da marca na fechadura.")


class TraceObservationContinuationTests(TestCase):
    """Testes do fluxo de vestígios após montagem da seção de local."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e laudo para coleta de vestígios."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_traces",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Traces",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _complete_metadata(self) -> CaseMetadata:
        """Retorna metadados completos para montagem sem prompts pendentes."""
        return CaseMetadata(
            report_number="9",
            report_year=2026,
            exam_objective="Examinar local.",
            requesting_authority="Dr. Silva",
            police_district="1º DP",
            occurrence_report="BO-9",
            police_inquiry="IP-9",
            designation_date=date(2026, 1, 15),
            occurrence_at=datetime(2026, 1, 10, 14, 30),
            requisition_at=datetime(2026, 1, 11, 10, 0),
            attendance_protocol="PROT-9",
            examination_at=datetime(2026, 1, 16, 9, 0),
            photography="N/I",
            scanning_3d="N/I",
            sketch="N/I",
        )

    def _store_test_image(self, report) -> ReportImage:
        """Persiste imagem JPEG mínima vinculada ao laudo."""
        buffer = BytesIO()
        Image.new("RGB", (40, 30), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        uploaded = SimpleUploadedFile("vestigio.jpg", buffer.read(), content_type="image/jpeg")
        return store_report_image(report, uploaded)

    def _bootstrap_property_scene_through_build(self, report):
        """Executa bootstrap até abrir coleta de vestígios."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        save_bootstrap_after_analyze(report, self._complete_metadata(), field_coverage={})

        state = bootstrap_state(report)
        while state not in (STATE_COLLECTING_SCENE_CONTINUATION, STATE_COLLECTING_TRACES):
            advance_forensic_body_build_step(report, examiner=self.examiner)
            report.refresh_from_db()
            state = bootstrap_state(report)

        if state == STATE_COLLECTING_SCENE_CONTINUATION:
            save_scene_examination_continuation(
                report,
                exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
                prompt="Porta da sala.",
                images=[],
            )
            report.refresh_from_db()

        state = bootstrap_state(report)
        while state == STATE_BUILDING:
            advance_forensic_body_build_step(report, examiner=self.examiner)
            report.refresh_from_db()
            state = bootstrap_state(report)

        self.assertEqual(state, STATE_COLLECTING_TRACES)

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content.generate_scene_examination_content"
    )
    def test_scene_build_transitions_to_traces_collection(self, mock_generate):
        """Garante abertura da coleta de vestígios após montagem do local patrimonial."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
            "report_images": [],
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        self._bootstrap_property_scene_through_build(report)

        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        self.assertTrue(bootstrap.get("traces_collection_active"))

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content.generate_scene_examination_content"
    )
    def test_skip_first_trace_opens_collected_items_stub(self, mock_generate):
        """Garante encerramento imediato com stub de objetos/peças quando o perito recusa vestígios."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
            "report_images": [],
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        self._bootstrap_property_scene_through_build(report)

        complete_traces_collection(report, skipped=True)
        report.refresh_from_db()

        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_COLLECTED_ITEMS)
        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        self.assertTrue(bootstrap.get("traces_skipped"))

    @patch(
        "institution_ic_sp.forensic_report.services.scene_examination_content.generate_scene_examination_content"
    )
    @patch(
        "institution_ic_sp.forensic_report.services.trace_observation_continuation.infer_trace_observation_content"
    )
    def test_trace_build_inserts_heading_once_and_image_nodes(self, mock_trace_infer, mock_generate):
        """Garante heading único e blocos IMAGE+legenda para vestígios registrados."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Equipe compareceu.",
            "characteristics_paragraph": "Imóvel residencial.",
            "report_images": [],
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        self._bootstrap_property_scene_through_build(report)

        report_image = self._store_test_image(report)

        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            advance_forensic_body_build_step,
        )

        for paragraph in (
            "Observa-se marca de ferramenta na fechadura.",
            "Identifica-se fragmento de tecido no piso.",
        ):
            mock_trace_infer.return_value = {
                "trace_paragraph": paragraph,
                "report_images": [
                    {
                        "image_id": str(report_image.pk),
                        "caption": "Detalhe do vestígio.",
                    }
                ],
            }
            save_trace_observation(
                report,
                prompt="Vestígio no local.",
                images=[
                    ReportImageAttachment(
                        image_id=str(report_image.pk),
                        show_in_report=True,
                        proposed_caption="Detalhe",
                    )
                ],
            )
            report.refresh_from_db()

            state = bootstrap_state(report)
            while state == STATE_BUILDING:
                advance_forensic_body_build_step(report, examiner=self.examiner)
                report.refresh_from_db()
                state = bootstrap_state(report)

        nodes = list(report.nodes.select_related("block").order_by("position"))
        heading_nodes = [
            node
            for node in nodes
            if node.block.block_type == ReportBlockType.HEADING
            and node.block.content.get("text") == TRACES_SECTION_HEADING
        ]
        self.assertEqual(len(heading_nodes), 1)

        image_nodes = [node for node in nodes if node.block.block_type == ReportBlockType.IMAGE]
        self.assertEqual(len(image_nodes), 2)

        trace_paragraphs = [
            node.block.content.get("text")
            for node in nodes
            if node.block.block_type == ReportBlockType.PARAGRAPH
            and node.block.content.get("text") in {
                "Observa-se marca de ferramenta na fechadura.",
                "Identifica-se fragmento de tecido no piso.",
            }
        ]
        self.assertEqual(
            trace_paragraphs,
            [
                "Observa-se marca de ferramenta na fechadura.",
                "Identifica-se fragmento de tecido no piso.",
            ],
        )

    def test_trace_decision_api_skips_collection(self):
        """Garante API de decisão encerrando vestígios na primeira recusa."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import attach_bootstrap_meta

        report.page_layout = attach_bootstrap_meta(
            report.page_layout,
            {
                "state": STATE_COLLECTING_TRACES,
                "traces_collection_active": True,
                "traces": [],
                "metadata": {"exam_category": EXAM_CATEGORY_PROPERTY_SCENE},
            },
        )
        report.save(update_fields=["page_layout", "updated_at"])

        self.client.force_login(self.user)
        url = reverse("reports:forensic_bootstrap_trace_decision", kwargs={"pk": report.pk})
        response = self.client.post(
            url,
            data='{"add_trace": false}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], STATE_COLLECTING_COLLECTED_ITEMS)
        self.assertIn("todo_message", payload)

    def test_trace_decision_api_returns_caption_numbers_when_numbering_enabled(self):
        """Garante mapa de legendas na resposta ao encerrar coleta de vestígios."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        report.number_captions = True
        report.save(update_fields=["number_captions", "updated_at"])
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import attach_bootstrap_meta

        report.page_layout = attach_bootstrap_meta(
            report.page_layout,
            {
                "state": STATE_COLLECTING_TRACES,
                "traces_collection_active": True,
                "traces": [],
                "metadata": {"exam_category": EXAM_CATEGORY_PROPERTY_SCENE},
            },
        )
        report.save(update_fields=["page_layout", "updated_at"])

        self.client.force_login(self.user)
        url = reverse("reports:forensic_bootstrap_trace_decision", kwargs={"pk": report.pk})
        response = self.client.post(
            url,
            data='{"add_trace": false}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("caption_numbers", payload)
        self.assertIsInstance(payload["caption_numbers"], dict)


class TraceAnchorResolverTests(TestCase):
    """Testes do ponto de inserção de vestígios na montagem incremental."""

    def test_resolve_traces_insert_anchor_prefers_last_mounted_trace(self):
        """Garante que novo vestígio entra após o último já montado, não após o local."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            _resolve_traces_insert_anchor,
        )

        node_registry = {
            "scene_report_images": "scene-last",
            "trace_body_0": "trace0-body",
            "trace_report_images_0": "trace0-images",
        }

        self.assertEqual(_resolve_traces_insert_anchor(node_registry), "trace0-images")

    def test_resolve_traces_insert_anchor_falls_back_to_scene(self):
        """Garante fallback para seção de local quando ainda não há vestígio montado."""
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            _resolve_traces_insert_anchor,
        )

        node_registry = {
            "scene_characteristics_body": "scene-body",
            "scene_report_images": "scene-images",
        }

        self.assertEqual(_resolve_traces_insert_anchor(node_registry), "scene-images")
