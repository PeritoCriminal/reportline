"""
Testes do model ReportBlock e opções de layout compartilhadas.

Valida tipos genéricos de conteúdo, valores padrão de formatação e
payload mínimo esperado para listas e links.
"""

import uuid

from django.test import TestCase

from reports.models import (
    ReportBlock,
    ReportBlockLineSpacing,
    ReportBlockType,
)


class ReportBlockModelTests(TestCase):
    """Testes de tipos e layout padrão de blocos de relatório."""

    def test_primary_key_is_uuid(self):
        """Garante que a chave primária do bloco seja UUID."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Texto."},
        )
        self.assertIsInstance(block.pk, uuid.UUID)

    def test_default_layout_options(self):
        """Garante valores padrão neutros de layout ao criar bloco."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Corpo."},
        )

        self.assertEqual(block.title_level, 0)
        self.assertFalse(block.page_break_before)
        self.assertFalse(block.keep_with_previous)
        self.assertFalse(block.keep_with_next)
        self.assertEqual(block.indent_level, 0)
        self.assertTrue(block.first_line_indent)
        self.assertEqual(block.line_spacing, ReportBlockLineSpacing.NORMAL)
        self.assertEqual(block.space_before, 0)
        self.assertEqual(block.space_after, 0)

    def test_link_block_content(self):
        """Garante persistência de bloco do tipo link com URL e rótulo."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.LINK,
            content={"text": "Acessar sistema", "url": "https://exemplo.gov.br"},
        )

        self.assertEqual(block.block_type, ReportBlockType.LINK)
        self.assertEqual(block.content["url"], "https://exemplo.gov.br")

    def test_ordered_list_block_content(self):
        """Garante persistência de lista numerada com itens ordenados."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.ORDERED_LIST,
            content={"items": ["Primeiro item", "Segundo item"]},
        )

        self.assertEqual(block.block_type, ReportBlockType.ORDERED_LIST)
        self.assertEqual(len(block.content["items"]), 2)

    def test_unordered_list_block_content(self):
        """Garante persistência de lista com marcadores."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": ["Marcador A", "Marcador B"]},
        )

        self.assertEqual(block.block_type, ReportBlockType.UNORDERED_LIST)

    def test_title_level_accepts_hierarchy(self):
        """Garante nível hierárquico configurável em blocos de título."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Subseção."},
            title_level=2,
            indent_level=2,
            first_line_indent=True,
            line_spacing=ReportBlockLineSpacing.RELAXED,
            space_before=6,
            space_after=12,
        )

        self.assertEqual(block.title_level, 2)
        self.assertEqual(block.indent_level, 2)
        self.assertEqual(block.line_spacing, ReportBlockLineSpacing.RELAXED)
        self.assertEqual(block.space_after, 12)
