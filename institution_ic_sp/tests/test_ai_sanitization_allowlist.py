# reportline/institution_ic_sp/tests/test_ai_sanitization_allowlist.py
"""
Testes da allowlist de termos preservados na sanitização para IA externa.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from common.privacy.services.sanitization_allowlist import (
    find_protected_spans,
    filter_analyzer_results,
)
from institution_ic_sp.forensic_report.common.ai.sanitization.forensic_sanitizer import (
    sanitize_forensic_text_for_external_ai,
)
from institution_ic_sp.forensic_report.common.ai.sanitization.sanitization_allowlist import (
    get_forensic_sanitization_allowlist,
)


class SanitizationAllowlistSpanTests(TestCase):
    """Testes de localização de termos institucionais protegidos."""

    def test_finds_autoridade_requisitante_span(self):
        """Garante localização de Autoridade Requisitante no texto."""
        text = "Autoridade Requisitante: Dr. João Silva"
        allowlist = ("autoridade requisitante",)
        spans = find_protected_spans(text, allowlist)
        self.assertTrue(spans)
        start, end = spans[0]
        self.assertEqual(text[start:end].lower(), "autoridade requisitante")

    def test_finds_croqui_with_accent_insensitive_match(self):
        """Garante correspondência insensível a acentos."""
        text = "Foi elaborado croqui do imóvel."
        spans = find_protected_spans(text, ("croqui",))
        self.assertEqual(len(spans), 1)
        self.assertEqual(text[spans[0][0]:spans[0][1]], "croqui")


class SanitizationAllowlistPresidioFilterTests(TestCase):
    """Testes de filtragem de detecções Presidio pela allowlist."""

    def test_filters_person_detection_on_protected_label(self):
        """Ignora detecção quando sobrepõe rótulo institucional protegido."""
        text = "Autoridade Requisitante: Dr. Silva"
        result = MagicMock(start=0, end=24, entity_type="PERSON")
        filtered = filter_analyzer_results(
            [result],
            text=text,
            allowlist=("autoridade requisitante",),
        )
        self.assertEqual(filtered, [])

    def test_keeps_person_detection_outside_protected_label(self):
        """Mantém detecção de nome fora dos termos protegidos."""
        text = "Autoridade Requisitante: Dr. Silva"
        result = MagicMock(start=28, end=37, entity_type="PERSON")
        filtered = filter_analyzer_results(
            [result],
            text=text,
            allowlist=("autoridade requisitante",),
        )
        self.assertEqual(len(filtered), 1)


@override_settings(FORENSIC_AI_SANITIZATION_ENABLED=True)
class ForensicSanitizationAllowlistIntegrationTests(TestCase):
    """Testes integrados da allowlist no pipeline forense."""

    @override_settings(
        FORENSIC_AI_SANITIZATION_ALLOWLIST="termo customizado",
    )
    def test_settings_extends_default_allowlist(self):
        """Garante inclusão de termos extras via settings."""
        allowlist = get_forensic_sanitization_allowlist()
        folded = {item.lower() for item in allowlist}
        self.assertIn("termo customizado", folded)
        self.assertIn("croqui", folded)

    @patch("common.privacy.services.text_sanitizer.get_analyzer_engine")
    def test_presidio_skips_protected_institutional_terms(self, mock_get_engine):
        """Garante que rótulos protegidos não são substituídos pelo Presidio."""
        mock_result = MagicMock(start=0, end=22, entity_type="PERSON")
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_engine.return_value = mock_analyzer

        text = "Autoridade Requisitante informada."
        result = sanitize_forensic_text_for_external_ai(text)

        self.assertIn("Autoridade Requisitante", result.sanitized_text)
        self.assertNotIn("[NOME_REMOVIDO]", result.sanitized_text)

    @patch("common.privacy.services.text_sanitizer.get_analyzer_engine")
    def test_presidio_still_redacts_unprotected_person_name(self, mock_get_engine):
        """Garante remoção de nome próprio fora da allowlist."""
        mock_result = MagicMock(start=11, end=22, entity_type="PERSON")
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = [mock_result]
        mock_get_engine.return_value = mock_analyzer

        text = "Compareceu Maria Souza ao local."
        result = sanitize_forensic_text_for_external_ai(text)

        self.assertIn("[NOME_REMOVIDO]", result.sanitized_text)
        self.assertNotIn("Maria Souza", result.sanitized_text)
