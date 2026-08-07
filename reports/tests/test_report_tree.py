# reportline/reports/tests/test_report_tree.py
"""
Testes do serviço de árvore de nós de relatório.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_tree import (
    append_list_item,
    delete_node,
    insert_sibling_after,
    insert_sibling_before,
    reorder_heading_siblings,
    update_node_block,
)

User = get_user_model()


class ReportTreeServiceTests(TestCase):
    """Testes de inserção e atualização de nós no editor."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório com bloco inicial."""
        cls.author = User.objects.create_user(
            username="tree_user",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Árvore")
        heading = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Título"},
            title_level=0,
        )
        cls.root = ReportNode.objects.create(
            report=cls.report,
            block=heading,
            position=Decimal("1"),
        )

    def test_insert_sibling_after_places_node_between_positions(self):
        """Garante posição fracionária ao inserir irmão após nó existente."""
        third_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Terceiro"},
        )
        ReportNode.objects.create(
            report=self.report,
            block=third_block,
            position=Decimal("3"),
        )

        new_node = insert_sibling_after(
            self.report,
            self.root,
            block_type=ReportBlockType.PARAGRAPH,
        )

        self.assertGreater(new_node.position, Decimal("1"))
        self.assertLess(new_node.position, Decimal("3"))
        self.assertEqual(new_node.block.block_type, ReportBlockType.PARAGRAPH)

    def test_update_node_block_persists_content(self):
        """Garante atualização do payload JSON do bloco."""
        update_node_block(self.root, content={"text": "Novo título"})

        self.root.block.refresh_from_db()
        self.assertEqual(self.root.block.content["text"], "Novo título")

    def test_append_list_item_adds_empty_entry(self):
        """Garante novo item vazio ao final da lista no mesmo nó."""
        list_block = ReportBlock.objects.create(
            block_type=ReportBlockType.ORDERED_LIST,
            content={"items": ["Primeiro"]},
        )
        list_node = ReportNode.objects.create(
            report=self.report,
            block=list_block,
            position=Decimal("2"),
        )

        _, new_index = append_list_item(list_node, items=["Primeiro", "Segundo"])

        list_node.block.refresh_from_db()
        self.assertEqual(
            list_node.block.content["items"],
            ["Primeiro", "Segundo", ""],
        )
        self.assertEqual(new_index, 2)

    def test_insert_sibling_rejects_foreign_report(self):
        """Garante erro ao inserir irmão com nó de outro relatório."""
        other_report = Report.objects.create(author=self.author, title="Outro")

        with self.assertRaises(ValidationError):
            insert_sibling_after(
                other_report,
                self.root,
                block_type=ReportBlockType.PARAGRAPH,
            )

    def test_insert_sibling_before_places_node_with_lower_position(self):
        """Garante posição fracionária ao inserir irmão antes do nó de referência."""
        new_node = insert_sibling_before(
            self.report,
            self.root,
            block_type=ReportBlockType.PARAGRAPH,
        )

        self.assertLess(new_node.position, self.root.position)

    def test_delete_node_removes_block(self):
        """Garante exclusão do nó e bloco quando há mais de um nó no relatório."""
        sibling = insert_sibling_after(
            self.report,
            self.root,
            block_type=ReportBlockType.PARAGRAPH,
        )
        sibling_id = sibling.pk
        block_id = sibling.block_id

        delete_node(sibling)

        self.assertFalse(ReportNode.objects.filter(pk=sibling_id).exists())
        self.assertFalse(ReportBlock.objects.filter(pk=block_id).exists())

    def test_delete_last_node_raises_validation_error(self):
        """Garante erro ao tentar excluir o único nó do relatório."""
        with self.assertRaises(ValidationError):
            delete_node(self.root)

    def test_reorder_heading_siblings_preserves_non_heading_between(self):
        """Garante reordenação de títulos mantendo parágrafos entre eles."""
        intro = self.root
        paragraph = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Corpo"},
        )
        paragraph_node = ReportNode.objects.create(
            report=self.report,
            block=paragraph,
            position=Decimal("2"),
        )
        conclusion_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Conclusão"},
            title_level=0,
        )
        conclusion = ReportNode.objects.create(
            report=self.report,
            block=conclusion_block,
            position=Decimal("3"),
        )

        reorder_heading_siblings(
            self.report,
            None,
            [conclusion.pk, intro.pk],
        )

        ordered = list(
            ReportNode.objects.filter(report=self.report, parent__isnull=True).order_by(
                "position"
            )
        )
        self.assertEqual(
            [node.pk for node in ordered],
            [conclusion.pk, paragraph_node.pk, intro.pk],
        )

    def test_reorder_heading_siblings_rejects_mismatched_ids(self):
        """Garante erro quando a lista enviada não corresponde aos títulos irmãos."""
        with self.assertRaises(ValidationError):
            reorder_heading_siblings(self.report, None, [])

    def test_reorder_heading_siblings_requires_two_headings(self):
        """Garante erro ao tentar reordenar com um único título."""
        with self.assertRaises(ValidationError):
            reorder_heading_siblings(self.report, None, [self.root.pk])

    def test_reorder_heading_siblings_rejects_heading_from_other_parent(self):
        """Garante erro ao tentar reordenar título de outro pai no mesmo payload."""
        parent_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Seção"},
        )
        parent_node = ReportNode.objects.create(
            report=self.report,
            block=parent_block,
            position=Decimal("2"),
        )
        child_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Filha"},
            title_level=1,
        )
        child_node = ReportNode.objects.create(
            report=self.report,
            parent=parent_node,
            block=child_block,
            position=Decimal("1"),
        )

        with self.assertRaises(ValidationError):
            reorder_heading_siblings(
                self.report,
                None,
                [self.root.pk, child_node.pk],
            )
