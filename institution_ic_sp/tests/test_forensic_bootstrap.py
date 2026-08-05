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
    STATE_PROMPTING,
    STATE_READY,
    STATE_SHELL_CREATED,
    bootstrap_state,
)
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import Report, ReportBlockType
from reports.services.report_kind import is_forensic_report

User = get_user_model()


class ForensicBootstrapPhaseOneTests(TestCase):
    """Testes da casca, análise e montagem do laudo pericial."""

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

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views.analyze_case_metadata_from_documents"
    )
    def test_bootstrap_build_populates_standard_body(self, mock_analyze):
        """Garante montagem do corpo padronizado após análise."""
        mock_analyze.return_value = CaseMetadata(
            report_number="9",
            report_year=2026,
            exam_objective="Examinar local.",
            occurrence_report="BO-9",
            police_district="1º DP",
            designation_date=date(2026, 1, 15),
            occurrence_at=datetime(2026, 1, 10, 14, 30),
            examination_at=datetime(2026, 1, 16, 9, 0),
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

        response = self.client.post(
            build_url,
            content_type="application/json",
            data="{}",
        )
        self.assertEqual(response.status_code, 200)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_READY)
        self.assertTrue(report.nodes.filter(block__block_type=ReportBlockType.HEADING).exists())
        self.assertTrue(report.nodes.filter(block__block_type=ReportBlockType.PARAGRAPH).exists())

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views.analyze_case_metadata_from_documents"
    )
    def test_bootstrap_build_enters_prompting_when_fields_missing(self, mock_analyze):
        """Garante estado prompting quando campos críticos permanecem vazios."""
        mock_analyze.return_value = CaseMetadata(report_year=2026)
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.client.post(build_url, content_type="application/json", data="{}")

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_PROMPTING)
        self.assertTrue(report.nodes.filter(block__block_type=ReportBlockType.HEADING).exists())

    def test_intake_page_exposes_quick_flow_assets(self):
        """Garante botão e script do fluxo rápido no template de intake."""
        self.client.login(username="perito_bootstrap", password="senha-segura")
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))

        self.assertContains(response, "btn-open-report-quick")
        self.assertContains(response, "case_intake_quick.js")
        self.assertContains(response, "Preencher ou revisar dados manualmente")

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views.analyze_case_metadata_from_documents"
    )
    def test_bootstrap_finalize_batch_skips_and_submits(self, mock_analyze):
        """Garante finalização em lote com skip e resposta única ao servidor."""
        mock_analyze.return_value = CaseMetadata(report_year=2026)
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.client.post(build_url, content_type="application/json", data="{}")

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_PROMPTING)

        response = self.client.post(
            finalize_url,
            data=json.dumps(
                {
                    "answers": {"report_number": "15"},
                    "skipped": [
                        "police_district",
                        "occurrence_report",
                        "designation_date",
                        "occurrence_at",
                        "examination_at",
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("reload"))
        self.assertEqual(payload.get("state"), STATE_READY)

        report.refresh_from_db()
        self.assertEqual(bootstrap_state(report), STATE_READY)
        self.assertIn("15/2026", report.title)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views.analyze_case_metadata_from_documents"
    )
    def test_bootstrap_finalize_rejects_incomplete_batch(self, mock_analyze):
        """Garante rejeição quando lote não cobre todos os prompts pendentes."""
        mock_analyze.return_value = CaseMetadata(report_year=2026)
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.client.post(build_url, content_type="application/json", data="{}")

        response = self.client.post(
            finalize_url,
            data=json.dumps({"answers": {"report_number": "15"}, "skipped": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views.analyze_case_metadata_from_documents"
    )
    def test_bootstrap_prompt_submit_updates_report_number(self, mock_analyze):
        """Garante atualização do título ao informar número do laudo no prompt."""
        mock_analyze.return_value = CaseMetadata(report_year=2026)
        self.client.login(username="perito_bootstrap", password="senha-segura")
        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)
        analyze_url = reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk})
        build_url = reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk})
        finalize_url = reverse("reports:forensic_bootstrap_finalize", kwargs={"pk": report.pk})

        self.client.post(analyze_url, {"documents": self._pdf_upload()})
        self.client.post(build_url, content_type="application/json", data="{}")

        response = self.client.post(
            finalize_url,
            data=json.dumps(
                {
                    "answers": {"report_number": "15"},
                    "skipped": [
                        "police_district",
                        "occurrence_report",
                        "designation_date",
                        "occurrence_at",
                        "examination_at",
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        report.refresh_from_db()
        self.assertIn("15/2026", report.title)
        main_title = report.nodes.filter(block__block_type=ReportBlockType.HEADING).order_by("position").first()
        self.assertIn("15/2026", main_title.block.content["text"])
