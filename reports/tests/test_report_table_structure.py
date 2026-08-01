"""
Testes de inserção e exclusão de linhas/colunas em tabelas.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.services.report_table_structure import (
    MAX_TABLE_BODY_ROWS,
    MAX_TABLE_COLUMNS,
    delete_column,
    delete_row,
    insert_column_after,
    insert_row_after,
)


def _sample_table(rows: int = 2, cols: int = 2) -> dict:
    """Monta tabela mínima para testes."""
    cell = {"type": "text", "text": ""}
    return {
        "headers": [f"H{i}" for i in range(cols)],
        "rows": [[{**cell, "text": f"R{row}C{col}"} for col in range(cols)] for row in range(rows)],
    }


class ReportTableStructureTests(TestCase):
    """Testes de mutações estruturais no JSON da tabela."""

    def test_insert_row_after_adds_empty_row(self):
        """Garante nova linha vazia após índice informado."""
        content = _sample_table(2, 2)
        updated = insert_row_after(content, 0)

        self.assertEqual(len(updated["rows"]), 3)
        self.assertEqual(updated["rows"][1], [{"type": "text", "text": ""}] * 2)

    def test_insert_row_from_header_uses_first_body_row(self):
        """Garante inserção abaixo do cabeçalho via índice -1."""
        content = _sample_table(1, 2)
        updated = insert_row_after(content, -1)

        self.assertEqual(len(updated["rows"]), 2)
        self.assertEqual(updated["rows"][0], [{"type": "text", "text": ""}] * 2)

    def test_insert_row_respects_maximum(self):
        """Garante erro ao exceder limite de linhas de corpo."""
        content = {
            "headers": ["A"],
            "rows": [[{"type": "text", "text": ""}]] * MAX_TABLE_BODY_ROWS,
        }

        with self.assertRaises(ValidationError):
            insert_row_after(content, 0)

    def test_delete_row_removes_line(self):
        """Garante remoção de linha do corpo."""
        content = _sample_table(2, 2)
        updated = delete_row(content, 0)

        self.assertEqual(len(updated["rows"]), 1)
        self.assertEqual(updated["rows"][0][0]["text"], "R1C0")

    def test_delete_row_keeps_minimum(self):
        """Garante erro ao tentar remover única linha de corpo."""
        content = _sample_table(1, 2)

        with self.assertRaises(ValidationError):
            delete_row(content, 0)

    def test_insert_column_after_adds_cells(self):
        """Garante nova coluna vazia após índice informado."""
        content = _sample_table(1, 2)
        updated = insert_column_after(content, 0)

        self.assertEqual(updated["headers"], ["H0", "", "H1"])
        self.assertEqual(len(updated["rows"][0]), 3)
        self.assertEqual(updated["rows"][0][1], {"type": "text", "text": ""})

    def test_insert_column_respects_maximum(self):
        """Garante erro ao exceder limite de colunas."""
        content = {
            "headers": [""] * MAX_TABLE_COLUMNS,
            "rows": [[{"type": "text", "text": ""}] * MAX_TABLE_COLUMNS],
        }

        with self.assertRaises(ValidationError):
            insert_column_after(content, 0)

    def test_delete_column_removes_cells(self):
        """Garante remoção de coluna e células correspondentes."""
        content = _sample_table(1, 3)
        updated = delete_column(content, 1)

        self.assertEqual(updated["headers"], ["H0", "H2"])
        self.assertEqual(updated["rows"][0][1]["text"], "R0C2")

    def test_delete_column_keeps_minimum(self):
        """Garante erro ao tentar remover única coluna."""
        content = _sample_table(1, 1)

        with self.assertRaises(ValidationError):
            delete_column(content, 0)

    def test_delete_column_cleans_image_cell_reference(self):
        """Garante que coluna com imagem pode ser removida na normalização."""
        content = {
            "headers": ["A", "B"],
            "rows": [[
                {"type": "text", "text": ""},
                {
                    "type": "image",
                    "alt": "",
                    "file": "reports/x/y.jpg",
                    "image_id": "img-1",
                    "width": 100,
                    "height": 50,
                },
            ]],
        }
        updated = delete_column(content, 1)

        self.assertEqual(len(updated["headers"]), 1)
        self.assertEqual(updated["rows"][0][0]["type"], "text")
