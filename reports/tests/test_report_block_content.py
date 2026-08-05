"""
Testes de normalização de conteúdo de blocos.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_content import (
    build_empty_table_content,
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

    def test_normalize_paragraph_sanitizes_inline_formatting(self):
        """Garante persistência segura de negrito e remoção de scripts no texto."""
        normalized = normalize_block_content(
            ReportBlockType.PARAGRAPH,
            {"text": '<strong>Corpo</strong><script>x</script>'},
        )
        self.assertEqual(normalized["text"], "<strong>Corpo</strong>x")

    def test_normalize_rejects_invalid_list_items(self):
        """Garante erro quando items não é lista."""
        with self.assertRaises(ValidationError):
            normalize_block_content(
                ReportBlockType.ORDERED_LIST,
                {"items": "invalido"},
            )

    def test_build_empty_table_content_includes_header_row(self):
        """Garante payload com cabeçalho e linhas conforme dimensões escolhidas."""
        content = build_empty_table_content(3, 4)

        self.assertEqual(
            content["headers"],
            [{"text": "", "align": "left"}] * 4,
        )
        self.assertEqual(len(content["rows"]), 2)
        self.assertEqual(
            content["rows"][0],
            [{"type": "text", "text": "", "align": "left"}] * 4,
        )
        self.assertEqual(content["column_widths"], [25, 25, 25, 25])
        self.assertEqual(content["display_width"], 100)

    def test_normalize_table_pads_short_rows(self):
        """Garante normalização de linhas menores que o número de colunas."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {
                "headers": ["A", "B"],
                "rows": [["1"]],
            },
        )

        self.assertEqual(
            normalized["rows"],
            [[
                {"type": "text", "text": "1", "align": "left"},
                {"type": "text", "text": "", "align": "left"},
            ]],
        )
        self.assertTrue(normalized["show_borders"])
        self.assertTrue(normalized["show_header"])

    def test_normalize_table_show_header_defaults_to_true(self):
        """Garante cabeçalho visível por padrão quando o campo não é enviado."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {"headers": ["A"], "rows": [[{"type": "text", "text": ""}]]},
        )

        self.assertTrue(normalized["show_header"])

    def test_normalize_table_show_header_can_be_hidden(self):
        """Garante persistência de tabela com cabeçalho oculto."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {
                "headers": ["A"],
                "rows": [[{"type": "text", "text": ""}]],
                "show_header": False,
            },
        )

        self.assertFalse(normalized["show_header"])

    def test_normalize_table_rejects_invalid_show_header(self):
        """Garante erro quando show_header não é booleano."""
        with self.assertRaises(ValidationError):
            normalize_block_content(
                ReportBlockType.TABLE,
                {
                    "headers": ["A"],
                    "rows": [[{"type": "text", "text": ""}]],
                    "show_header": "nao",
                },
            )

    def test_normalize_table_without_headers_uses_row_column_count(self):
        """Garante tabela sem cabeçalho preserve colunas do corpo (ex.: localização com QR)."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {
                "headers": [],
                "rows": [
                    [
                        {"type": "text", "text": "QR", "align": "center"},
                        {"type": "text", "text": "Endereço", "align": "left"},
                    ]
                ],
                "show_borders": False,
                "show_header": False,
                "column_widths": [35, 65],
                "display_width": 100,
            },
        )

        self.assertEqual(len(normalized["rows"]), 1)
        self.assertEqual(len(normalized["rows"][0]), 2)
        self.assertEqual(normalized["column_widths"], [35, 65])
        self.assertFalse(normalized["show_header"])

    def test_normalize_table_show_borders_defaults_to_true(self):
        """Garante bordas visíveis por padrão quando o campo não é enviado."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {"headers": ["A"], "rows": [[{"type": "text", "text": ""}]]},
        )

        self.assertTrue(normalized["show_borders"])

    def test_normalize_table_show_borders_can_be_hidden(self):
        """Garante persistência de tabela com linhas ocultas."""
        normalized = normalize_block_content(
            ReportBlockType.TABLE,
            {
                "headers": ["A"],
                "rows": [[{"type": "text", "text": ""}]],
                "show_borders": False,
            },
        )

        self.assertFalse(normalized["show_borders"])

    def test_normalize_table_rejects_invalid_show_borders(self):
        """Garante erro quando show_borders não é booleano."""
        with self.assertRaises(ValidationError):
            normalize_block_content(
                ReportBlockType.TABLE,
                {
                    "headers": ["A"],
                    "rows": [[{"type": "text", "text": ""}]],
                    "show_borders": "sim",
                },
            )

    def test_normalize_image_includes_metadata(self):
        """Garante normalização de bloco de imagem com metadados de exibição."""
        normalized = normalize_block_content(
            ReportBlockType.IMAGE,
            {
                "alt": "Figura 1",
                "file": "reports/abc/photo.jpg",
                "image_id": "uuid-1",
                "width": 454,
                "height": 300,
            },
        )

        self.assertEqual(normalized["alt"], "Figura 1")
        self.assertEqual(normalized["image_id"], "uuid-1")
        self.assertEqual(normalized["width"], 454)
        self.assertEqual(normalized["height"], 300)

    def test_normalize_image_accepts_display_resize(self):
        """Garante que dimensões menores que o original são aceitas no bloco."""
        normalized = normalize_block_content(
            ReportBlockType.IMAGE,
            {
                "alt": "",
                "file": "reports/abc/photo.jpg",
                "image_id": "uuid-1",
                "width": 200,
                "height": 150,
            },
        )

        self.assertEqual(normalized["width"], 200)
        self.assertEqual(normalized["height"], 150)

    def test_default_content_for_horizontal_rule_is_empty(self):
        """Garante payload vazio para linha horizontal."""
        self.assertEqual(
            default_content_for_block_type(ReportBlockType.HORIZONTAL_RULE),
            {},
        )

    def test_normalize_horizontal_rule_rejects_content(self):
        """Garante que linha horizontal não aceita campos de conteúdo."""
        with self.assertRaises(ValidationError):
            normalize_block_content(
                ReportBlockType.HORIZONTAL_RULE,
                {"text": "invalido"},
            )

    def test_normalize_horizontal_rule_accepts_empty_payload(self):
        """Garante persistência de linha horizontal com JSON vazio."""
        self.assertEqual(
            normalize_block_content(ReportBlockType.HORIZONTAL_RULE, {}),
            {},
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
