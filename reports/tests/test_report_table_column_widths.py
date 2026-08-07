# reportline/reports/tests/test_report_table_column_widths.py
"""
Testes de larguras de colunas em tabelas.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.services.report_table_column_widths import (
    equal_column_widths,
    merge_column_width,
    normalize_column_widths,
    resize_adjacent_columns,
    split_column_width,
)


class ReportTableColumnWidthsTests(TestCase):
    """Testes de percentuais de largura por coluna."""

    def test_equal_column_widths_sums_to_100(self):
        """Garante distribuição igual somando 100%."""
        self.assertEqual(sum(equal_column_widths(3)), 100)
        self.assertEqual(equal_column_widths(3), [34, 33, 33])

    def test_normalize_column_widths_rescales_to_100(self):
        """Garante reescala proporcional quando a soma difere de 100."""
        normalized = normalize_column_widths([20, 20, 20], 3)

        self.assertEqual(sum(normalized), 100)

    def test_normalize_column_widths_defaults_when_missing(self):
        """Garante larguras iguais quando a lista não é enviada."""
        normalized = normalize_column_widths(None, 2)

        self.assertEqual(normalized, [50, 50])

    def test_normalize_column_widths_rejects_invalid_values(self):
        """Garante erro quando algum valor não é inteiro."""
        with self.assertRaises(ValidationError):
            normalize_column_widths(["a", 50], 2)

    def test_split_column_width_divides_target_column(self):
        """Garante divisão da coluna ao inserir nova coluna."""
        updated = split_column_width([60, 40], 0)

        self.assertEqual(updated, [30, 30, 40])

    def test_merge_column_width_adds_to_neighbor(self):
        """Garante que largura removida retorna ao vizinho."""
        updated = merge_column_width([30, 30, 40], 1)

        self.assertEqual(updated, [30, 70])

    def test_resize_adjacent_columns_respects_minimum(self):
        """Garante largura mínima por coluna durante redimensionamento."""
        updated = resize_adjacent_columns([50, 50], 0, 48)

        self.assertEqual(updated, [95, 5])

    def test_resize_adjacent_columns_transfers_width(self):
        """Garante transferência de percentual entre colunas adjacentes."""
        updated = resize_adjacent_columns([50, 50], 0, 10)

        self.assertEqual(updated, [60, 40])
