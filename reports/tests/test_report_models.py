# reportline/reports/tests/test_report_models.py
"""
Testes dos models Report, ReportNode e ReportBlock.

Valida vínculo autor-relatório, árvore de nós, associação 1:1 com bloco
e remoção em cascata do bloco ao excluir o nó.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import (
    Report,
    ReportBlock,
    ReportBlockType,
    ReportNode,
    ReportStatus,
)

User = get_user_model()


class ReportModelTests(TestCase):
    """Testes do model Report e vínculo com CustomUser."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuário autor para cenários de relatório."""
        cls.author = User.objects.create_user(
            username="autor1",
            password="senha-segura",
        )

    def test_primary_key_is_uuid(self):
        """Garante que a chave primária do relatório seja UUID."""
        report = Report.objects.create(
            author=self.author,
            title="Relatório de teste",
        )
        self.assertIsInstance(report.pk, uuid.UUID)

    def test_default_status_is_draft(self):
        """Garante status inicial rascunho ao criar relatório."""
        report = Report.objects.create(
            author=self.author,
            title="Rascunho",
        )
        self.assertEqual(report.status, ReportStatus.DRAFT)

    def test_author_supports_multiple_reports(self):
        """Garante relação 1:N entre usuário e relatórios."""
        Report.objects.create(author=self.author, title="Primeiro")
        Report.objects.create(author=self.author, title="Segundo")

        self.assertEqual(self.author.reports.count(), 2)

    def test_save_populates_author_snapshot(self):
        """Garante snapshot textual do autor ao persistir relatório vinculado."""
        self.author.first_name = "Maria"
        self.author.last_name = "Silva"
        self.author.save()

        report = Report.objects.create(
            author=self.author,
            title="Com snapshot",
        )

        self.assertEqual(report.author_username, "autor1")
        self.assertEqual(report.author_display_name, "Maria Silva")

    def test_deleting_author_preserves_report_and_snapshot(self):
        """Garante que exclusão do usuário mantém relatório com dados textuais."""
        self.author.first_name = "João"
        self.author.last_name = "Santos"
        self.author.save()

        report = Report.objects.create(
            author=self.author,
            title="Laudo preservado",
        )
        report_id = report.pk

        self.author.delete()

        report.refresh_from_db()
        self.assertTrue(Report.objects.filter(pk=report_id).exists())
        self.assertIsNone(report.author_id)
        self.assertEqual(report.author_username, "autor1")
        self.assertEqual(report.author_display_name, "João Santos")
        self.assertEqual(report.author_label, "João Santos")


class ReportNodeModelTests(TestCase):
    """Testes da árvore de nós e blocos associados."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório base e blocos para composição."""
        cls.author = User.objects.create_user(
            username="autor2",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Laudo estruturado",
        )

    def _create_node(self, block_type, content, parent=None, position=Decimal("0")):
        """Cria nó com bloco genérico para cenários de teste."""
        block = ReportBlock.objects.create(
            block_type=block_type,
            content=content,
        )
        return ReportNode.objects.create(
            report=self.report,
            parent=parent,
            block=block,
            position=position,
        )

    def test_node_block_one_to_one(self):
        """Garante associação exclusiva entre nó e bloco de conteúdo."""
        node = self._create_node(
            ReportBlockType.HEADING,
            {"level": 1, "text": "Introdução"},
        )

        self.assertEqual(node.block.block_type, ReportBlockType.HEADING)
        self.assertEqual(node.block.node, node)

    def test_tree_parent_child_relationship(self):
        """Garante hierarquia pai-filho entre nós do mesmo relatório."""
        root = self._create_node(
            ReportBlockType.HEADING,
            {"level": 0, "text": "Número do laudo"},
            position=Decimal("0"),
        )
        child = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Corpo do parágrafo."},
            parent=root,
            position=Decimal("1"),
        )

        self.assertIsNone(root.parent)
        self.assertEqual(child.parent, root)
        self.assertIn(child, root.children.all())

    def test_sibling_ordering_by_position(self):
        """Garante ordenação de nós irmãos pelo campo position."""
        second = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Segundo"},
            position=Decimal("2"),
        )
        first = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Primeiro"},
            position=Decimal("1"),
        )

        ordered_ids = list(
            self.report.nodes.order_by("position").values_list("pk", flat=True)
        )
        self.assertEqual(ordered_ids, [first.pk, second.pk])

    def test_deleting_node_removes_associated_block(self):
        """Garante exclusão do bloco ao remover o nó correspondente."""
        node = self._create_node(
            ReportBlockType.TABLE,
            {"headers": ["Coluna A"], "rows": []},
        )
        block_id = node.block_id

        node.delete()

        self.assertFalse(ReportBlock.objects.filter(pk=block_id).exists())
        self.assertFalse(ReportNode.objects.filter(pk=node.pk).exists())

    def test_deleting_report_cascades_to_nodes(self):
        """Garante remoção dos nós ao excluir o relatório."""
        node = self._create_node(
            ReportBlockType.IMAGE,
            {"alt": "Evidência", "file": "evidencia.jpg"},
        )
        block_id = node.block_id
        report_id = self.report.pk

        self.report.delete()

        self.assertFalse(Report.objects.filter(pk=report_id).exists())
        self.assertFalse(ReportNode.objects.filter(pk=node.pk).exists())
        self.assertFalse(ReportBlock.objects.filter(pk=block_id).exists())
