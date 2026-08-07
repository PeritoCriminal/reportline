# reportline/reports/tests/test_report_table_display_width.py
"""Testes de largura de exibição de tabelas no editor."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_content import build_empty_table_content, normalize_block_content
from reports.services.report_table_display_width import (
    DEFAULT_TABLE_DISPLAY_WIDTH,
    MAX_TABLE_DISPLAY_WIDTH,
    MIN_TABLE_DISPLAY_WIDTH,
    normalize_display_width,
)


class ReportTableDisplayWidthTests(TestCase):
    """Testes de normalização da largura total da tabela."""

    def test_defaults_to_full_width(self):
        """Garante largura padrão de 100% quando ausente."""
        self.assertEqual(normalize_display_width(None), DEFAULT_TABLE_DISPLAY_WIDTH)

    def test_accepts_valid_percent(self):
        """Garante persistência de percentual válido."""
        self.assertEqual(normalize_display_width(65), 65)

    def test_rejects_below_minimum(self):
        """Garante erro abaixo do mínimo permitido."""
        with self.assertRaises(ValidationError):
            normalize_display_width(MIN_TABLE_DISPLAY_WIDTH - 1)

    def test_rejects_above_maximum(self):
        """Garante erro acima do máximo permitido."""
        with self.assertRaises(ValidationError):
            normalize_display_width(MAX_TABLE_DISPLAY_WIDTH + 1)

    def test_table_content_includes_display_width(self):
        """Garante normalização de display_width no payload da tabela."""
        content = normalize_block_content(
            ReportBlockType.TABLE,
            build_empty_table_content(2, 2),
        )
        self.assertEqual(content["display_width"], 100)

    def test_table_content_normalizes_custom_display_width(self):
        """Garante persistência de largura customizada no JSON."""
        content = normalize_block_content(
            ReportBlockType.TABLE,
            {
                **build_empty_table_content(2, 2),
                "display_width": 60,
            },
        )
        self.assertEqual(content["display_width"], 60)
