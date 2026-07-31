"""
Testes do serviço de contexto do editor de relatório.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_editor_context import build_report_editor_context

User = get_user_model()


class ReportEditorContextTests(TestCase):
    """Testes da montagem de sumário e corpo para o editor."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório com árvore de nós para os cenários."""
        cls.author = User.objects.create_user(
            username="editor1",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Laudo de exemplo",
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

    def test_outline_includes_only_headings_in_tree_order(self):
        """Garante sumário apenas com títulos respeitando hierarquia de nós."""
        intro = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Introdução"},
            position=Decimal("1"),
        )
        self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Texto introdutório."},
            parent=intro,
            position=Decimal("1"),
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Conclusão"},
            position=Decimal("2"),
        )

        context = build_report_editor_context(self.report)

        self.assertEqual(len(context["outline_tree"]), 2)
        self.assertEqual(context["outline_tree"][0].label, "Introdução")
        self.assertEqual(context["outline_tree"][1].label, "Conclusão")

    def test_outline_promotes_heading_under_non_heading_parent(self):
        """Garante título filho de parágrafo no mesmo nível visual do pai ignorado."""
        root_heading = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Seção principal"},
            position=Decimal("1"),
        )
        paragraph = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Corpo."},
            parent=root_heading,
            position=Decimal("1"),
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Subseção"},
            parent=paragraph,
            position=Decimal("1"),
        )

        context = build_report_editor_context(self.report)

        self.assertEqual(len(context["outline_tree"]), 1)
        self.assertEqual(len(context["outline_tree"][0].children), 1)
        self.assertEqual(context["outline_tree"][0].children[0].label, "Subseção")

    def test_body_entries_follow_depth_first_reading_order(self):
        """Garante ordem de leitura profundidade-primeiro no corpo do relatório."""
        first = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Parte 1"},
            position=Decimal("1"),
        )
        second = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Detalhe."},
            parent=first,
            position=Decimal("1"),
        )
        third = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Encerramento."},
            position=Decimal("2"),
        )

        context = build_report_editor_context(self.report)
        node_ids = [entry.node_id for entry in context["body_entries"]]

        self.assertEqual(node_ids, [first.pk, second.pk, third.pk])

    def test_empty_report_returns_empty_structures(self):
        """Garante estruturas vazias quando relatório não possui nós."""
        empty_report = Report.objects.create(
            author=self.author,
            title="Vazio",
        )

        context = build_report_editor_context(empty_report)

        self.assertEqual(context["outline_tree"], [])
        self.assertEqual(context["body_entries"], [])

    def test_outline_entry_primary_key_is_uuid(self):
        """Garante identificador UUID nos itens do sumário para âncoras estáveis."""
        node = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Capítulo"},
        )

        context = build_report_editor_context(self.report)

        self.assertIsInstance(context["outline_tree"][0].node_id, uuid.UUID)
        self.assertEqual(context["outline_tree"][0].node_id, node.pk)
