# reportline/institution_ic_sp/tests/test_metadata_inference_sanitization.py
"""
Testes da sanitização seletiva na inferência de metadados administrativos.
"""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from institution_ic_sp.forensic_report.workflows.initial_data.ai.services.metadata_inference import (
    infer_case_metadata_ai_payload,
)


@override_settings(
    OPENAI_API_KEY="test-key",
    FORENSIC_AI_SANITIZATION_ENABLED=True,
)
class MetadataInferenceSanitizationTests(TestCase):
    """Testes de higienização apenas em trechos documentais."""

    @patch(
        "institution_ic_sp.forensic_report.workflows.initial_data.ai.services"
        ".metadata_inference.complete_json_chat_safe"
    )
    @patch(
        "institution_ic_sp.forensic_report.workflows.initial_data.ai.services"
        ".metadata_inference.sanitize_uploaded_document_text"
    )
    @patch(
        "institution_ic_sp.forensic_report.workflows.initial_data.ai.services"
        ".metadata_inference.extract_text_from_uploads"
    )
    def test_only_document_excerpts_are_sanitized(
        self,
        mock_extract,
        mock_sanitize,
        mock_complete,
    ):
        """Garante sanitização do documento e preservação do prompt complementar."""
        mock_extract.return_value = "Texto bruto do PDF com CPF 111.222.333-44"
        mock_sanitize.return_value = "Texto higienizado do PDF"
        mock_complete.return_value = {"exam_objective": "Examinar local."}

        infer_case_metadata_ai_payload(
            uploaded_files=[
                SimpleUploadedFile("req.pdf", b"%PDF-1.4", content_type="application/pdf")
            ],
            supplementary_prompt="Perito informa: jose da silva na Rua das acacias",
        )

        mock_sanitize.assert_called_once_with(
            "Texto bruto do PDF com CPF 111.222.333-44",
            audit_context=None,
        )
        sent_user = mock_complete.call_args.kwargs["user"]
        self.assertIn("Texto higienizado do PDF", sent_user)
        self.assertIn("jose da silva na Rua das acacias", sent_user)
