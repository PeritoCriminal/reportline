"""Testes de recuo de parágrafos (nível e primeira linha)."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_indent import (
    MAX_INDENT_LEVEL,
    default_first_line_indent_for_block,
    default_indent_level_for_block,
    normalize_indent_level,
)


class ReportBlockIndentTests(TestCase):
    """Testes de normalização e defaults de recuo de parágrafo."""

    def test_normalize_indent_level_accepts_valid_range(self):
        """Garante aceitação de níveis entre 0 e o máximo permitido."""
        self.assertEqual(normalize_indent_level(0), 0)
        self.assertEqual(normalize_indent_level(MAX_INDENT_LEVEL), MAX_INDENT_LEVEL)

    def test_normalize_indent_level_rejects_out_of_range(self):
        """Garante rejeição de nível acima do máximo."""
        with self.assertRaises(ValidationError):
            normalize_indent_level(MAX_INDENT_LEVEL + 1)

    def test_default_first_line_indent_for_body_paragraph(self):
        """Garante recuo de primeira linha ligado por padrão em parágrafos de corpo."""
        self.assertTrue(
            default_first_line_indent_for_block(ReportBlockType.PARAGRAPH)
        )

    def test_default_first_line_indent_off_for_caption(self):
        """Garante legendas sem recuo de primeira linha."""
        self.assertFalse(
            default_first_line_indent_for_block(
                ReportBlockType.PARAGRAPH,
                is_caption=True,
            )
        )

    def test_default_indent_level_is_zero(self):
        """Garante parágrafos iniciam sem recuo de bloco."""
        self.assertEqual(
            default_indent_level_for_block(ReportBlockType.PARAGRAPH),
            0,
        )
