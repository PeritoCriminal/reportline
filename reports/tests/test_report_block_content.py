"""
Testes de normalização de conteúdo de blocos.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_content import (
    default_content_for_block_type,
    normalize_block_content,
)
from reports.services.report_block_sequence import get_next_sibling_block_type


class ReportBlockContentTests(TestCase):
    """Testes de payloads JSON por tipo de bloco."""

    def test_default_content_for_heading_is_empty_text(self):
        """Garante payload inicial vazio para título."""
        self.assertEqual(
            default_content_for_block_type(ReportBlockType.HEADING),
            {"text": ""},
        )

    def test_normalize_rejects_invalid_list_items(self):
        """Garante erro quando items não é lista."""
        with self.assertRaises(ValidationError):
            normalize_block_content(
                ReportBlockType.ORDERED_LIST,
                {"items": "invalido"},
            )


class ReportBlockSequenceTests(TestCase):
    """Testes de sequência de blocos após Enter."""

    def test_heading_followed_by_paragraph(self):
        """Garante parágrafo após título."""
        self.assertEqual(
            get_next_sibling_block_type(ReportBlockType.HEADING),
            ReportBlockType.PARAGRAPH,
        )

    def test_image_followed_by_paragraph_caption(self):
        """Garante parágrafo após imagem para legenda."""
        self.assertEqual(
            get_next_sibling_block_type(ReportBlockType.IMAGE),
            ReportBlockType.PARAGRAPH,
        )
