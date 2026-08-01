"""
Testes de normalização de células de tabela.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_content import normalize_block_content
from reports.services.report_table_cell_content import (
    collect_image_ids_from_table_content,
    normalize_table_body_cell,
    normalize_table_header_cell,
)


class ReportTableCellContentTests(TestCase):
    """Testes de células de texto e imagem em tabelas."""

    def test_normalize_header_accepts_string(self):
        """Garante compatibilidade com cabeçalhos em string."""
        self.assertEqual(
            normalize_table_header_cell("Coluna A"),
            {"text": "Coluna A", "align": "left"},
        )

    def test_normalize_body_cell_legacy_string(self):
        """Garante compatibilidade com células legadas em string."""
        self.assertEqual(
            normalize_table_body_cell("Texto"),
            {"type": "text", "text": "Texto", "align": "left"},
        )

    def test_normalize_body_cell_image(self):
        """Garante normalização de célula com imagem embutida."""
        normalized = normalize_table_body_cell(
            {
                "type": "image",
                "alt": "",
                "file": "reports/1/photo.jpg",
                "image_id": "abc",
                "width": 120,
                "height": 80,
            }
        )

        self.assertEqual(normalized["type"], "image")
        self.assertEqual(normalized["width"], 120)

    def test_normalize_table_with_image_cell(self):
        """Garante tabela com célula de imagem no corpo."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {
                "headers": ["A", "B"],
                "rows": [
                    [
                        {"type": "text", "text": "1"},
                        {
                            "type": "image",
                            "alt": "",
                            "file": "reports/1/photo.jpg",
                            "image_id": "img-1",
                            "width": 100,
                            "height": 60,
                        },
                    ],
                ],
            },
        )

        self.assertEqual(normalized["rows"][0][1]["type"], "image")
        self.assertEqual(normalized["rows"][0][0]["text"], "1")

    def test_collect_image_ids_from_table(self):
        """Garante extração de IDs de imagens embutidas na tabela."""
        ids = collect_image_ids_from_table_content(
            {
                "rows": [
                    [
                        {"type": "text", "text": ""},
                        {"type": "image", "image_id": "img-1", "file": "x.jpg"},
                    ],
                ],
            }
        )

        self.assertEqual(ids, ["img-1"])

    def test_normalize_rejects_image_in_header(self):
        """Garante que cabeçalho não aceita imagem."""
        with self.assertRaises(ValidationError):
            normalize_table_header_cell({"type": "image", "file": "x.jpg"})
