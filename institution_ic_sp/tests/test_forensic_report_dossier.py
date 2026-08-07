"""
Testes do dossiê pericial persistido (fase initial_data).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import EXAM_CATEGORY_PROPERTY_SCENE
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_READY,
    attach_bootstrap_meta,
)
from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
    INITIAL_DATA_PHASE,
    build_initial_data_phase_payload,
    build_property_crime_phase_payload,
    get_forensic_report_metadata,
    initial_data_phase_from_dossier,
    persist_initial_data_phase,
    property_crime_phase_from_dossier,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.models import ForensicReportMetadata, ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()

ANALYZE_PATCH = (
    "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views"
    ".analyze_case_metadata_with_coverage"
)


class ForensicReportDossierPhaseOneTests(TestCase):
    """Testes de persistência da fase initial_data no dossiê pericial."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e equipe para fluxo de bootstrap."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_dossier",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Dossier",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    @staticmethod
    def _pdf_upload() -> SimpleUploadedFile:
        """Retorna PDF mínimo para upload em memória."""
        return SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 dossier test",
            content_type="application/pdf",
        )

    @staticmethod
    def _analyze_return(
        metadata: CaseMetadata,
        *,
        extensions: dict[str, object] | None = None,
    ) -> tuple[CaseMetadata, dict[str, str], dict[str, object]]:
        """Empacota metadados simulados como retorno da análise."""
        return metadata, {"report_number": "full", "occurrence_at": "datetime"}, dict(extensions or {})

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

    def test_persist_initial_data_phase_creates_dossier_record(self):
        """Garante criação do registro de dossiê ao fechar a fase administrativa."""
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
            supplementary_prompt="Priorizar requisição.",
        )
        metadata = CaseMetadata(
            report_number="7",
            report_year=2026,
            exam_objective="Examinar local.",
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            supplementary_prompt="Priorizar requisição.",
        )

        dossier = persist_initial_data_phase(report, metadata)

        self.assertIsInstance(dossier, ForensicReportMetadata)
        self.assertEqual(dossier.report_id, report.pk)
        self.assertEqual(dossier.data["exam_category"], EXAM_CATEGORY_PROPERTY_SCENE)
        phase = dossier.data["phases"][INITIAL_DATA_PHASE]
        self.assertEqual(phase["inputs"]["supplementary_prompt"], "Priorizar requisição.")
        self.assertEqual(phase["data"]["report_number"], "7")
        self.assertEqual(phase["data"]["extensions"], {})

    def test_build_field_provenance_marks_manual_and_skipped_fields(self):
        """Garante origem manual e skipped na montagem do payload da fase."""
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import attach_bootstrap_meta
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import empty_bootstrap_payload

        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = empty_bootstrap_payload()
        bootstrap["skipped_prompts"] = ["photography"]
        bootstrap["manual_prompt_fields"] = ["report_number"]
        bootstrap["document_count"] = 2
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        metadata = CaseMetadata(report_number="15", report_year=2026, photography="")
        payload = build_initial_data_phase_payload(report, metadata)

        self.assertEqual(payload["inputs"]["document_count"], 2)
        self.assertIn("photography", payload["meta"]["skipped_fields"])
        self.assertEqual(payload["meta"]["field_provenance"]["report_number"], "manual")
        self.assertEqual(payload["meta"]["field_provenance"]["photography"], "skipped")

    @patch(ANALYZE_PATCH)
    def test_initial_build_completion_persists_dossier_via_bootstrap_flow(self, mock_analyze):
        """Garante gravação do dossiê ao concluir montagem administrativa no editor."""
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
                occurrence_at=timezone.make_aware(datetime(2026, 1, 10, 14, 30)),
                requisition_at=timezone.make_aware(datetime(2026, 1, 11, 10, 0)),
                attendance_protocol="PROT-9",
                examination_at=timezone.make_aware(datetime(2026, 1, 16, 9, 0)),
                photography="N/I",
                scanning_3d="N/I",
                sketch="N/I",
                exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            )
        )
        self.client.login(username="perito_dossier", password="senha-segura")
        report = create_forensic_report_shell(
            author=self.user,
            examiner=self.examiner,
            supplementary_prompt="Usar BO anexo.",
        )
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})

        response = self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.assertEqual(response.status_code, 200)

        self._run_incremental_build_until(
            report.pk,
            stop_states={STATE_COLLECTING_SCENE_CONTINUATION},
        )

        dossier = get_forensic_report_metadata(report)
        self.assertIsNotNone(dossier)
        phase = initial_data_phase_from_dossier(report)
        self.assertIsNotNone(phase)
        self.assertEqual(phase["inputs"]["document_count"], 1)
        self.assertEqual(phase["inputs"]["supplementary_prompt"], "Usar BO anexo.")
        self.assertEqual(phase["data"]["report_number"], "9")
        self.assertEqual(phase["data"]["occurrence_report"], "BO-9")
        self.assertIn("confirmed_at", phase["meta"])

    @patch(ANALYZE_PATCH)
    def test_dossier_not_created_before_initial_build_completion(self, mock_analyze):
        """Garante ausência de dossiê enquanto a fase administrativa não foi fechada."""
        mock_analyze.return_value = self._analyze_return(
            CaseMetadata(report_number="1", report_year=2026, exam_objective="Examinar.")
        )
        self.client.login(username="perito_dossier", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})

        self.assertIsNone(get_forensic_report_metadata(report))

    @patch(ANALYZE_PATCH)
    def test_finalize_prompts_records_manual_provenance_in_dossier(self, mock_analyze):
        """Garante proveniência manual quando o perito responde prompt antes da montagem."""
        mock_analyze.return_value = self._analyze_return(CaseMetadata(report_year=2026))
        self.client.login(username="perito_dossier", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.client.post(
            finalize_url,
            data=json.dumps(
                {
                    "answers": {"report_number": "88"},
                    "skipped": [
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
                    ],
                }
            ),
            content_type="application/json",
        )

        metadata = CaseMetadata(report_number="88", report_year=2026)
        report.refresh_from_db()
        persist_initial_data_phase(report, metadata)

        phase = initial_data_phase_from_dossier(report)
        self.assertEqual(phase["meta"]["field_provenance"]["report_number"], "manual")


SCENE_CONTENT_PATCH = (
    "institution_ic_sp.forensic_report.services.scene_examination_content"
    ".generate_scene_examination_content"
)


class ForensicReportDossierPhaseTwoTests(TestCase):
    """Testes de persistência da fase property_crime no dossiê pericial."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e equipe para fluxo de bootstrap."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_dossier_phase2",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Dossier Phase2",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    @staticmethod
    def _pdf_upload() -> SimpleUploadedFile:
        """Retorna PDF mínimo para upload em memória."""
        return SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 dossier phase2 test",
            content_type="application/pdf",
        )

    @staticmethod
    def _analyze_return(
        metadata: CaseMetadata,
        *,
        extensions: dict[str, object] | None = None,
    ) -> tuple[CaseMetadata, dict[str, str], dict[str, object]]:
        """Empacota metadados simulados como retorno da análise."""
        return metadata, {}, dict(extensions or {})

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

    def test_build_property_crime_phase_payload_includes_inputs_and_content(self):
        """Garante montagem do payload da fase property_crime a partir do bootstrap."""
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["scene_characteristics"] = {
            "prompt": "Portão basculante danificado.",
            "image_ids": ["img-1"],
            "location": {
                "kind": "address",
                "address": "Rua Exemplo, 10",
                "latitude": "",
                "longitude": "",
            },
        }
        bootstrap["scene_examination_content"] = {
            "characteristics_heading": "Características do Imóvel",
            "attendance_context_paragraph": "A equipe compareceu ao local.",
            "characteristics_paragraph": "Imóvel residencial térreo.",
        }
        bootstrap["scene_attendance_context"] = {
            "location_preserved": "yes",
            "police_authority_present": "no",
            "investigation_team_present": "yes",
            "access_granted_by": "proprietário",
            "informant_provided_info": "yes",
            "informant_briefing": "Informou que o local permanecia fechado.",
        }
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        metadata = CaseMetadata(
            report_number="3",
            report_year=2026,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
        )
        persist_initial_data_phase(report, metadata)

        payload = build_property_crime_phase_payload(report, metadata)

        self.assertEqual(payload["inputs"]["scene_prompt"], "Portão basculante danificado.")
        self.assertEqual(payload["inputs"]["image_ids"], ["img-1"])
        self.assertEqual(payload["inputs"]["location"]["address"], "Rua Exemplo, 10")
        self.assertEqual(payload["data"]["characteristics_heading"], "Características do Imóvel")
        self.assertIn("initial_data", payload["meta"]["sources_used"])
        self.assertIn("scene_prompt", payload["meta"]["sources_used"])
        self.assertIn("images", payload["meta"]["sources_used"])
        self.assertIn("location", payload["meta"]["sources_used"])
        self.assertEqual(payload["inputs"]["attendance_context"]["location_preserved"], "yes")
        self.assertIn("attendance_context", payload["meta"]["sources_used"])

    @patch(SCENE_CONTENT_PATCH)
    @patch(ANALYZE_PATCH)
    def test_scene_build_completion_persists_property_crime_phase(self, mock_analyze, mock_generate):
        """Garante gravação da fase property_crime ao concluir montagem de exame de local."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Compareceu a equipe pericial.",
            "characteristics_paragraph": "Casa térrea com muro alto.",
        }
        mock_analyze.return_value = self._analyze_return(
            CaseMetadata(
                report_number="5",
                report_year=2026,
                exam_objective="Examinar local de furto.",
                exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
                requesting_authority="Dr. Silva",
                police_district="1º DP",
                occurrence_report="BO-5",
                police_inquiry="IP-5",
                designation_date=date(2026, 1, 15),
                occurrence_at=timezone.make_aware(datetime(2026, 1, 10, 14, 30)),
                requisition_at=timezone.make_aware(datetime(2026, 1, 11, 10, 0)),
                attendance_protocol="PROT-5",
                examination_at=timezone.make_aware(datetime(2026, 1, 16, 9, 0)),
                photography="N/I",
                scanning_3d="N/I",
                sketch="N/I",
            )
        )
        self.client.login(username="perito_dossier_phase2", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        scene_url = reverse("reports:forensic_bootstrap_scene_continuation", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self._run_incremental_build_until(
            report.pk,
            stop_states={STATE_COLLECTING_SCENE_CONTINUATION},
        )
        self.client.post(
            scene_url,
            data=json.dumps(
                {
                    "exam_category": EXAM_CATEGORY_PROPERTY_SCENE,
                    "prompt": "Fachada com portão metálico.",
                    "image_ids": ["img-scene-1"],
                    "location": {
                        "kind": "address",
                        "address": "Rua Teste, 10",
                    },
                }
            ),
            content_type="application/json",
        )
        self._run_incremental_build_until(report.pk, stop_states={STATE_READY})

        dossier = get_forensic_report_metadata(report)
        self.assertIsNotNone(dossier)
        self.assertIn(INITIAL_DATA_PHASE, dossier.data["phases"])
        phase = property_crime_phase_from_dossier(report)
        self.assertIsNotNone(phase)
        self.assertEqual(phase["inputs"]["scene_prompt"], "Fachada com portão metálico.")
        self.assertEqual(phase["inputs"]["image_ids"], ["img-scene-1"])
        self.assertEqual(phase["inputs"]["location"]["address"], "Rua Teste, 10")
        self.assertEqual(phase["data"]["attendance_context_paragraph"], "Compareceu a equipe pericial.")
        self.assertEqual(phase["data"]["characteristics_paragraph"], "Casa térrea com muro alto.")
        self.assertIn("confirmed_at", phase["meta"])

    @patch(SCENE_CONTENT_PATCH)
    def test_property_crime_phase_not_created_before_scene_build_completion(self, mock_generate):
        """Garante ausência da fase property_crime antes da montagem da seção de local."""
        mock_generate.return_value = {
            "characteristics_heading": "Características do Local",
            "attendance_context_paragraph": "Compareceu a equipe.",
            "characteristics_paragraph": "Casa térrea.",
        }
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        metadata = CaseMetadata(
            report_number="2",
            report_year=2026,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
        )
        persist_initial_data_phase(report, metadata)

        from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
            save_scene_examination_continuation,
        )

        bootstrap = report.page_layout["reportline_meta"]["bootstrap"]
        bootstrap["initial_build_completed"] = True
        bootstrap["scene_insert_after_node_id"] = "node-anchor"
        bootstrap["nodes"] = {"attendance_list": "node-anchor"}
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        report.save(update_fields=["page_layout", "updated_at"])

        save_scene_examination_continuation(
            report,
            exam_category=EXAM_CATEGORY_PROPERTY_SCENE,
            prompt="Entrada lateral.",
            image_ids=[],
        )
        report.refresh_from_db()

        self.assertIsNone(property_crime_phase_from_dossier(report))
