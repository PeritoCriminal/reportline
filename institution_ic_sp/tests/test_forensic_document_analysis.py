"""
Testes da análise documental AJAX do intake comum.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class AnalyzeDocumentsViewTests(TestCase):
    """Testes do endpoint de pré-preenchimento por IA."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito criminal autenticável."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.examiner_user = User.objects.create_user(
            username="perito_analyze",
            password="senha-segura",
        )
        cls.regular_user = User.objects.create_user(
            username="comum_analyze",
            password="senha-segura",
        )
        ForensicExaminerSP.objects.create(
            user=cls.examiner_user,
            forensic_team=cls.team,
            display_name="Dr. Analyze",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes."""
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:analyze_documents"),
        )
        self.assertEqual(response.status_code, 302)

    def test_user_without_profile_receives_404(self):
        """Garante 404 para usuário autenticado sem perfil pericial."""
        self.client.login(username="comum_analyze", password="senha-segura")
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:analyze_documents"),
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_documents_returns_bad_request(self):
        """Garante erro quando nenhum documento é enviado."""
        self.client.login(username="perito_analyze", password="senha-segura")
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:analyze_documents"),
            {"report_number": "10"},
        )
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content)
        self.assertIn("documento", payload["error"].lower())

    @override_settings(OPENAI_API_KEY="")
    @patch(
        "institution_ic_sp.forensic_report.common.ai.document_text._extract_pdf_text",
        return_value="Boletim de ocorrência BO-999",
    )
    def test_analyze_without_ai_key_returns_warning(self, _mock_extract):
        """Garante aviso quando IA não está configurada."""
        self.client.login(username="perito_analyze", password="senha-segura")
        upload = SimpleUploadedFile(
            "bo.pdf",
            b"%PDF stub",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:analyze_documents"),
            {
                "report_number": "",
                "report_year": "2026",
                "documents": upload,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(any("OPENAI_API_KEY" in warning for warning in payload["warnings"]))

    @override_settings(OPENAI_API_KEY="test-key")
    @patch(
        "institution_ic_sp.forensic_report.common.ai.document_text._extract_pdf_text",
        return_value="Requisição da Delegacia Central",
    )
    @patch(
        "institution_ic_sp.forensic_report.common.services.case_metadata_extraction.infer_case_metadata_ai_payload",
        return_value={
            "report_number": "99",
            "report_year": 2026,
            "occurrence_report": "BO-IA",
            "requesting_authority": "Dr. Delegado IA",
            "extensions": {"exam_location_address": "Rua Teste, 1"},
        },
    )
    def test_analyze_merges_ai_payload_preserving_manual_fields(
        self,
        _mock_payload,
        _mock_extract,
    ):
        """Garante mescla manual > inferido na resposta JSON."""
        self.client.login(username="perito_analyze", password="senha-segura")
        upload = SimpleUploadedFile(
            "req.pdf",
            b"%PDF stub",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:analyze_documents"),
            {
                "report_number": "7",
                "report_year": "2026",
                "requesting_authority": "Dr. Manual",
                "documents": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        metadata = payload["metadata"]
        self.assertEqual(metadata["report_number"], "7")
        self.assertEqual(metadata["requesting_authority"], "Dr. Manual")
        self.assertEqual(metadata["occurrence_report"], "BO-IA")
        self.assertEqual(
            payload["extensions"]["exam_location_address"],
            "Rua Teste, 1",
        )

    def test_intake_page_hides_manual_preview_and_advanced_form(self):
        """Garante que pré-visualização e formulário avançado permanecem ocultos no intake."""
        self.client.login(username="perito_analyze", password="senha-segura")
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))
        self.assertNotContains(response, "Pré-visualizar metadados nos campos avançados")
        self.assertNotContains(response, "case_intake_analyze.js")
        self.assertNotContains(response, "Preencher ou revisar dados manualmente")
        self.assertContains(response, "case_intake_documents.js")
        self.assertContains(response, "intake-documents-dropzone")
        self.assertContains(response, "case_intake_analyze.css")
        self.assertContains(response, "btn-open-report-quick")
        self.assertNotContains(response, " com IA")
