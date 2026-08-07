# reportline/reports/tests/test_report_block_alignment.py
"""Testes de alinhamento de blocos e células no editor."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import ReportBlockType
from reports.services.report_block_alignment import (
    default_text_align_for_block,
    default_text_align_for_table_cell,
    normalize_text_align,
)
from reports.services.report_block_content import build_empty_table_content, normalize_block_content
from reports.services.report_table_cell_content import (
    normalize_table_body_cell,
    normalize_table_header_cell,
)


class ReportBlockAlignmentTests(TestCase):
    """Testes de defaults e normalização de alinhamento."""

    def test_main_title_heading_is_center(self):
        """Garante título principal (sem numeração) centralizado por padrão."""
        self.assertEqual(
            default_text_align_for_block(
                ReportBlockType.HEADING,
                is_main_title=True,
            ),
            "center",
        )

    def test_numbered_heading_is_left(self):
        """Garante títulos numerados alinhados à esquerda por padrão."""
        self.assertEqual(
            default_text_align_for_block(
                ReportBlockType.HEADING,
                is_main_title=False,
            ),
            "left",
        )

    def test_subheading_level_does_not_force_center(self):
        """Garante que nível hierárquico sozinho não centraliza título numerado."""
        self.assertEqual(
            default_text_align_for_block(
                ReportBlockType.HEADING,
                title_level=0,
                is_main_title=False,
            ),
            "left",
        )

    def test_default_paragraph_is_justify(self):
        """Garante parágrafos justificados por padrão."""
        self.assertEqual(default_text_align_for_block(ReportBlockType.PARAGRAPH), "justify")

    def test_default_caption_is_center(self):
        """Garante legendas centralizadas por padrão."""
        self.assertEqual(
            default_text_align_for_block(ReportBlockType.PARAGRAPH, is_caption=True),
            "center",
        )

    def test_default_list_is_left(self):
        """Garante listas alinhadas à esquerda por padrão."""
        self.assertEqual(default_text_align_for_block(ReportBlockType.ORDERED_LIST), "left")

    def test_default_image_is_center(self):
        """Garante imagens centralizadas por padrão."""
        self.assertEqual(default_text_align_for_block(ReportBlockType.IMAGE), "center")

    def test_normalize_rejects_invalid_align(self):
        """Garante erro para valor de alinhamento inválido."""
        with self.assertRaises(ValidationError):
            normalize_text_align("top")

    def test_table_header_cell_stores_align(self):
        """Garante persistência de alinhamento em cabeçalho de tabela."""
        normalized = normalize_table_header_cell({"text": "Coluna", "align": "center"})
        self.assertEqual(normalized["text"], "Coluna")
        self.assertEqual(normalized["align"], "center")

    def test_table_body_text_cell_defaults_left(self):
        """Garante célula de texto com alinhamento esquerdo padrão."""
        normalized = normalize_table_body_cell({"type": "text", "text": "A"})
        self.assertEqual(normalized["align"], "left")

    def test_table_body_image_cell_defaults_center(self):
        """Garante imagem em célula centralizada por padrão."""
        normalized = normalize_table_body_cell(
            {
                "type": "image",
                "alt": "",
                "file": "reports/x.jpg",
                "image_id": "1",
                "width": 100,
                "height": 50,
            }
        )
        self.assertEqual(normalized["align"], "center")

    def test_empty_table_content_headers_are_objects(self):
        """Garante cabeçalhos normalizados como objetos com alinhamento."""
        content = normalize_block_content(
            ReportBlockType.TABLE,
            build_empty_table_content(2, 2),
        )
        self.assertEqual(content["headers"][0]["text"], "")
        self.assertEqual(content["headers"][0]["align"], "left")
