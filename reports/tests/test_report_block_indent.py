# reportline/reports/tests/test_report_block_indent.py
"""Testes de recuo de parágrafos (nível e primeira linha)."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlock, ReportBlockType, ReportNode
from reports.models.report_block import ReportBlockLineSpacing
from reports.services.report_block_indent import (
    MAX_INDENT_LEVEL,
    default_first_line_indent_for_block,
    default_indent_level_for_block,
    normalize_indent_level,
    normalize_line_spacing,
    validate_paragraph_indent_patch,
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

    def test_validate_indent_patch_allows_lists(self):
        """Garante que listas numeradas e com marcadores aceitam recuo de bloco."""
        for block_type in (
            ReportBlockType.ORDERED_LIST,
            ReportBlockType.UNORDERED_LIST,
        ):
            block = ReportBlock(
                block_type=block_type,
                content={"items": ["Item"]},
            )
            node = ReportNode(block=block)
            validate_paragraph_indent_patch(node, indent_level=2, first_line_indent=None)

    def test_validate_indent_patch_rejects_list_line_spacing(self):
        """Garante que espaçamento entre linhas não se aplica a listas."""
        block = ReportBlock(
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": ["Item"]},
        )
        node = ReportNode(block=block)
        with self.assertRaises(ValidationError):
            validate_paragraph_indent_patch(
                node,
                indent_level=None,
                first_line_indent=None,
                line_spacing=ReportBlockLineSpacing.COMPACT,
            )

    def test_normalize_line_spacing_accepts_supported_values(self):
        """Garante aceitação de espaçamento simples, 1,2 e 1,5."""
        self.assertEqual(
            normalize_line_spacing(ReportBlockLineSpacing.COMPACT),
            ReportBlockLineSpacing.COMPACT,
        )
        self.assertEqual(
            normalize_line_spacing(ReportBlockLineSpacing.SNUG),
            ReportBlockLineSpacing.SNUG,
        )
        self.assertEqual(
            normalize_line_spacing(ReportBlockLineSpacing.NORMAL),
            ReportBlockLineSpacing.NORMAL,
        )

    def test_normalize_line_spacing_rejects_invalid_value(self):
        """Garante rejeição de valor de espaçamento inválido."""
        with self.assertRaises(ValidationError):
            normalize_line_spacing("double")
