# reportline/institution_ic_sp/tests/test_ai_gateway.py
"""
Testes do gateway de IA externa com sanitização seletiva.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from common.privacy.exceptions import ExternalAiBlockedError
from institution_ic_sp.forensic_report.common.ai.gateway import (
    complete_json_chat_safe,
    sanitize_uploaded_document_text,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


@override_settings(
    OPENAI_API_KEY="test-key",
    FORENSIC_AI_SANITIZATION_ENABLED=True,
    FORENSIC_AI_BLOCK_ON_RESIDUAL_PII=True,
)
class AiGatewaySanitizationTests(TestCase):
    """Testes de sanitização documental e preservação de prompts no gateway."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito para contexto de auditoria."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_gateway",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Gateway",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_sanitize_uploaded_document_text_removes_cpf(self):
        """Garante que CPF em documento anexado é removido antes do envio externo."""
        sanitized = sanitize_uploaded_document_text(
            "CPF do envolvido: 123.456.789-00",
            audit_context={
                "operation": "metadata_extraction",
                "user_id": str(self.user.pk),
            },
        )

        self.assertIn("[CPF_REMOVIDO]", sanitized)
        self.assertNotIn("123.456.789-00", sanitized)

    @patch("institution_ic_sp.forensic_report.common.ai.gateway.complete_json_chat")
    def test_gateway_preserves_prompt_text_without_sanitization(self, mock_complete):
        """Garante que texto de caixas de prompt não é sanitizado na chamada final."""
        mock_complete.return_value = {"ok": True}

        payload = complete_json_chat_safe(
            system="Extraia metadados.",
            user="Informações complementares: CPF 123.456.789-00 na Rua das Flores",
            audit_context={
                "operation": "metadata_extraction",
                "user_id": str(self.user.pk),
            },
        )

        self.assertEqual(payload, {"ok": True})
        mock_complete.assert_called_once()
        sent_user = mock_complete.call_args.kwargs["user"]
        self.assertIn("123.456.789-00", sent_user)
        self.assertIn("Rua das Flores", sent_user)

    def test_sanitize_uploaded_document_blocks_when_sanitization_fails(self):
        """Garante bloqueio quando PII residual impede envio externo do documento."""
        with patch(
            "institution_ic_sp.forensic_report.common.ai.gateway"
            ".sanitize_forensic_text_for_external_ai"
        ) as mock_sanitize:
            from common.privacy.dataclasses import SanitizationResult

            mock_sanitize.return_value = SanitizationResult(
                sanitized_text="texto",
                blocked=True,
                block_reason="Bloqueado para teste.",
                content_hash="abc",
            )
            with self.assertRaises(ExternalAiBlockedError):
                sanitize_uploaded_document_text(
                    "Documento com PII",
                    audit_context={"operation": "test"},
                )
