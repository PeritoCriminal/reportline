"""
Testes do bootstrap interativo de laudos periciais (Fase 1).
"""

from unittest.mock import patch

import json

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_ANALYZED,
    STATE_BUILDING,
    STATE_COLLECTING_PROMPTS,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_PROMPTING,
    STATE_READY,
    STATE_SHELL_CREATED,
    bootstrap_state,
)
from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_TRAFFIC_ACCIDENT
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import Report, ReportBlockType
from reports.services.report_kind import is_forensic_report

User = get_user_model()


ANALYZE_PATCH = (
    "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
    ".analyze_case_metadata_with_coverage"
)


class ForensicBootstrapPhaseOneTests(TestCase):
    """Testes da casca, análise e montagem do laudo pericial."""

    @staticmethod
    def _prompt_skips_without_report_number() -> list[str]:
        """Lista campos puláveis exceto número do laudo nos testes de finalize."""
        return [
            "exam_objective",
            "requesting_authority",
            "police_district",
            "occurrence_report",
            "police_inquiry",
            "designation_date",
            "occurrence_at",
            "requisition_at",
            "attendance_protocol",
            "examination_at",
            "photography",
            "scanning_3d",
            "sketch",
        ]

    @staticmethod
    def _analyze_return(
        metadata: CaseMetadata,
        *,
        extensions: dict[str, object] | None = None,
    ) -> tuple[CaseMetadata, dict[str, str], dict[str, object]]:
        """Empacota metadados simulados como retorno da análise com cobertura."""
        return metadata, {}, dict(extensions or {})

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e URLs de bootstrap."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_bootstrap",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Bootstrap",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def _pdf_upload(self) -> SimpleUploadedFile:
        """Retorna PDF mínimo para upload em memória."""
        return SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 bootstrap test",
            content_type="application/pdf",
        )

    def _complete_scene_continuation(self, report_pk, *, category=EXAM_CATEGORY_TRAFFIC_ACCIDENT):
        """Conclui etapa de continuação de exame de local nos testes de bootstrap."""
        return self.client.post(
            reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report_pk}),
            data=json.dumps({"exam_category": category}),
            content_type="application/json",
        )

    def _run_incremental_build_until(self, report_pk, *, stop_states):
        """Executa passos incrementais até atingir um dos estados informados."""
        build_step_url = reverse("reports:forensic_bootstrap_build_step", kwargs={"pk": report_pk})
        last_response = None
        for _ in range(40):
            last_response = self.client.post(
                build_step_url,
                content_type="application/json",
                data="{}",
            )
            payload = last_response.json()
            if payload.get("state") in stop_states:
                break
            if payload.get("done"):
                break
        return last_response

    def test_quick_shell_creates_forensic_report_without_body(self):
        """Garante criação de casca institucional sem blocos de corpo."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
            supplementary_prompt="Prioridade alta.",
        )

        self.assertTrue(is_forensic_report(report))
        self.assertEqual(bootstrap_state(report), STATE_SHELL_CREATED)
        self.assertEqual(report.nodes.count(), 0)
        self.assertTrue(report.page_layout["header"]["enabled"])

    def test_quick_shell_endpoint_returns_bootstrap_urls(self):
        """Garante endpoint JSON de casca com URLs de análise e montagem."""
        self.client.login(username="perito_bootstrap", password="senha-segura")
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:quick_shell"),
            {"supplementary_prompt": "Teste"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        report = Report.objects.get(pk=payload["report_id"])
        self.assertEqual(
            payload["analyze_url"],
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
        )
        self.assertEqual(
            payload["build_url"],
            reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk}),
        )

    @patch(ANALYZE_PATCH)
    def test_bootstrap_build_populates_standard_body(self, mock_analyze):
        """Garante montagem do corpo padronizado após análise."""
        mock_analyze.return_value = self._analyze_return(
            CaseMetadata(
                report_number="9",
                report_year=2026,
                exam_objective="Examinar local.",
                requesting_authority="Dr. Silva",
                occurrence_report="BO-9",
                police_inquiry="IP-9",
                police_district="1º DP",
                designation_date=date(2026, 1, 15),
                occurrence_at=datetime(2026, 1, 10, 14, 30),
                requisition_at=datetime(2026, 1, 11, 10, 0),
                attendance_protocol="PROT-9",
                examination_at=datetime(2026, 1, 16, 9, 0),
                photography="N/I",
                scanning_3d="N/I",
                sketch="N/I",
            )
        )
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
        )
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})

        response = self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.assertEqual(response.status_code, 200)
        mock_analyze.assert_called_once()
        self._run_incremental_build_until(
            report.pk,
            stop_states={STATE_COLLECTING_SCENE_CONTINUATION},
        )
        self._complete_scene_continuation(report.pk)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_READY)
        self.assertTrue(report.nodes.filter(block__block_type=ReportBlockType.HEADING).exists())
        self.assertTrue(report.nodes.filter(block__block_type=ReportBlockType.PARAGRAPH).exists())

    @patch(ANALYZE_PATCH)
    def test_bootstrap_analyze_enters_collecting_prompts_when_fields_missing(self, mock_analyze):
        """Garante coleta de prompts após análise quando campos críticos permanecem vazios."""
        mock_analyze.return_value = self._analyze_return(CaseMetadata(report_year=2026))
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})

        response = self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("state"), STATE_COLLECTING_PROMPTS)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_PROMPTS)

        status_response = self.client.get(
            reverse("reports:forensic_bootstrap_status", kwargs={"pk": report.pk})
        )
        status_payload = status_response.json()
        self.assertTrue(status_payload.get("pending_prompts"))
        self.assertEqual(report.nodes.count(), 0)

    def test_intake_page_exposes_quick_flow_assets(self):
        """Garante botão e script do fluxo rápido no template de intake."""
        self.client.login(username="perito_bootstrap", password="senha-segura")
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))

        self.assertContains(response, "btn-open-report-quick")
        self.assertContains(response, "case_intake_quick.js")
        self.assertContains(response, "case_intake_documents.js")
        self.assertContains(response, "intake-documents-dropzone")
        self.assertContains(response, "Arraste documentos aqui ou clique para selecionar")
        self.assertContains(response, "forensic_bootstrap_documents.js")
        self.assertNotContains(response, "Preencher ou revisar dados manualmente")
        self.assertNotContains(response, "Pré-visualizar metadados nos campos avançados")
        self.assertNotContains(response, " com IA")

    def test_editor_exposes_runner_config_when_shell_created(self):
        """Garante URLs de bootstrap no editor quando laudo está em casca."""
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        response = self.client.get(reverse("reports:edit", kwargs={"pk": report.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "forensic_bootstrap_runner.js")
        self.assertContains(response, "scene_examination_continuation.js")
        self.assertContains(response, "scene-location-analyze-status")
        self.assertContains(response, "Analisar imagens e orientações")
        self.assertNotContains(response, " com IA")
        self.assertContains(response, "case_intake_analyze.css")
        self.assertContains(response, "forensic-bootstrap-build-shell")
        self.assertContains(
            response,
            reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
        )

    @patch(ANALYZE_PATCH)
    def test_bootstrap_build_step_returns_block_html(self, mock_analyze):
        """Garante montagem incremental com HTML parcial por passo."""
        mock_analyze.return_value = self._analyze_return(
            CaseMetadata(
                report_number="3",
                report_year=2026,
                exam_objective="Examinar.",
                requesting_authority="Dr. Silva",
                occurrence_report="BO-3",
                police_inquiry="IP-3",
                police_district="1º DP",
                designation_date=date(2026, 1, 15),
                occurrence_at=datetime(2026, 1, 10, 14, 30),
                requisition_at=datetime(2026, 1, 11, 9, 0),
                attendance_protocol="PROT-3",
                examination_at=datetime(2026, 1, 16, 9, 0),
                photography="N/I",
                scanning_3d="N/I",
                sketch="N/I",
            )
        )
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_step_url = reverse("reports:forensic_bootstrap_build_step", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        response = self.client.post(build_step_url, content_type="application/json", data="{}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("step_id"), "main_title")
        self.assertTrue(payload.get("blocks_html"))
        self.assertIn("report-editor-block", payload["blocks_html"][0])
        self.assertFalse(payload.get("done"))

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_BUILDING)
        self.assertEqual(report.nodes.count(), 1)

    @patch(ANALYZE_PATCH)
    def test_bootstrap_build_step_finalize_returns_success(self, mock_analyze):
        """Garante resposta 200 no último passo da montagem inicial (regressão NameError)."""
        mock_analyze.return_value = self._analyze_return(
            CaseMetadata(
                report_number="3",
                report_year=2026,
                exam_objective="Examinar.",
                requesting_authority="Dr. Silva",
                occurrence_report="BO-3",
                police_inquiry="IP-3",
                police_district="1º DP",
                designation_date=date(2026, 1, 15),
                occurrence_at=datetime(2026, 1, 10, 14, 30),
                requisition_at=datetime(2026, 1, 11, 9, 0),
                attendance_protocol="PROT-3",
                examination_at=datetime(2026, 1, 16, 9, 0),
                photography="N/I",
                scanning_3d="N/I",
                sketch="N/I",
            )
        )
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_step_url = reverse("reports:forensic_bootstrap_build_step", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        last_response = None
        for _ in range(40):
            last_response = self.client.post(
                build_step_url,
                content_type="application/json",
                data="{}",
            )
            self.assertEqual(last_response.status_code, 200)
            payload = last_response.json()
            if payload.get("done"):
                break

        self.assertIsNotNone(last_response)
        payload = last_response.json()
        self.assertTrue(payload.get("done"))
        self.assertEqual(payload.get("state"), STATE_COLLECTING_SCENE_CONTINUATION)
        self.assertEqual(payload.get("step_id"), "finalize")
        self.assertIn("scene_continuation_config", payload)
        scene_config = payload["scene_continuation_config"]
        self.assertIn("pendingAttendanceContextPrompts", scene_config)
        self.assertGreater(len(scene_config["pendingAttendanceContextPrompts"]), 0)
        self.assertIn("attendanceContextFinalizeUrl", scene_config)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_SCENE_CONTINUATION)
        self.assertGreater(report.nodes.count(), 0)

    def test_bootstrap_build_rejects_shell_without_analyze(self):
        """Garante que montagem exige análise prévia dos documentos."""
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})

        response = self.client.post(build_url, content_type="application/json", data="{}")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(bootstrap_state(report), STATE_SHELL_CREATED)

    @patch(ANALYZE_PATCH)
    def test_bootstrap_finalize_batch_skips_and_submits(self, mock_analyze):
        """Garante finalização em lote antes da montagem com skip e resposta única."""
        mock_analyze.return_value = self._analyze_return(CaseMetadata(report_year=2026))
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_COLLECTING_PROMPTS)

        response = self.client.post(
            finalize_url,
            data=json.dumps(
                {
                    "answers": {"report_number": "15"},
                    "skipped": self._prompt_skips_without_report_number(),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload.get("reload"))
        self.assertEqual(payload.get("state"), STATE_ANALYZED)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_ANALYZED)
        self.assertEqual(report.nodes.count(), 0)

        self._run_incremental_build_until(
            report.pk,
            stop_states={STATE_COLLECTING_SCENE_CONTINUATION},
        )
        self._complete_scene_continuation(report.pk)
        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_READY)
        self.assertIn("15/2026", report.title)

    @patch(ANALYZE_PATCH)
    def test_bootstrap_finalize_rejects_incomplete_batch(self, mock_analyze):
        """Garante rejeição quando lote não cobre todos os prompts pendentes."""
        mock_analyze.return_value = self._analyze_return(CaseMetadata(report_year=2026))
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        response = self.client.post(
            finalize_url,
            data=json.dumps({"answers": {"report_number": "15"}, "skipped": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch(ANALYZE_PATCH)
    def test_bootstrap_prompt_submit_updates_report_number(self, mock_analyze):
        """Garante atualização do título ao informar número do laudo no prompt."""
        mock_analyze.return_value = self._analyze_return(CaseMetadata(report_year=2026))
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        response = self.client.post(
            finalize_url,
            data=json.dumps(
                {
                    "answers": {"report_number": "15"},
                    "skipped": self._prompt_skips_without_report_number(),
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        self._run_incremental_build_until(
            report.pk,
            stop_states={STATE_COLLECTING_SCENE_CONTINUATION},
        )
        self._complete_scene_continuation(report.pk)
        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_READY)
        self.assertIn("15/2026", report.title)
