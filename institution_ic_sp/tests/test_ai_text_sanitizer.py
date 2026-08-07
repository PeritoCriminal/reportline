# reportline/institution_ic_sp/tests/test_ai_text_sanitizer.py
"""
Testes de sanitização de PII antes de envio a IA externa.
"""

from django.test import TestCase, override_settings

from institution_ic_sp.forensic_report.common.ai.sanitization.forensic_sanitizer import (
    sanitize_forensic_text_for_external_ai,
)


@override_settings(FORENSIC_AI_SANITIZATION_ENABLED=True)
class ForensicTextSanitizerTests(TestCase):
    """Testes do pipeline local de sanitização pericial."""

    def test_cpf_is_removed(self):
        """Garante remoção de CPF formatado antes de envio externo."""
        result = sanitize_forensic_text_for_external_ai("CPF 123.456.789-00")
        self.assertIn("[CPF_REMOVIDO]", result.sanitized_text)
        self.assertNotIn("123.456.789-00", result.sanitized_text)
        self.assertFalse(result.blocked)

    def test_bo_number_is_removed(self):
        """Garante remoção de número de BO."""
        result = sanitize_forensic_text_for_external_ai("Registro BO-12345/2026")
        self.assertIn("[NUMERO_REMOVIDO]", result.sanitized_text)
        self.assertNotIn("BO-12345", result.sanitized_text)

    def test_technical_text_without_pii_is_not_blocked(self):
        """Garante que texto técnico sem PII permanece utilizável."""
        text = "LEVANTAMENTO DE LOCAL - FURTO A RESIDENCIA"
        result = sanitize_forensic_text_for_external_ai(text)
        self.assertFalse(result.blocked)
        self.assertIn("LEVANTAMENTO DE LOCAL", result.sanitized_text)

    def test_bo_number_is_fully_redacted(self):
        """Garante substituição completa de número de BO."""
        result = sanitize_forensic_text_for_external_ai("Documento BO-99999/2026")
        self.assertFalse(result.blocked)
        self.assertNotIn("BO-99999", result.sanitized_text)
