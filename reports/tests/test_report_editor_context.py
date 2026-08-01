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

    def _create_node(
        self,
        block_type,
        content,
        parent=None,
        position=Decimal("0"),
        title_level=0,
    ):
        """Cria nó com bloco genérico para cenários de teste."""
        block = ReportBlock.objects.create(
            block_type=block_type,
            content=content,
            title_level=title_level,
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

    def test_outline_nests_headings_by_title_level_in_reading_order(self):
        """Garante hierarquia visual do sumário por title_level, não por pai de nó."""
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Teste"},
            position=Decimal("1"),
            title_level=0,
        )
        section = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Seção um"},
            position=Decimal("2"),
            title_level=0,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Subseção 1.1"},
            position=Decimal("3"),
            title_level=1,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Subseção 1.2"},
            position=Decimal("4"),
            title_level=1,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Seção dois"},
            position=Decimal("5"),
            title_level=0,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Subnível 4"},
            position=Decimal("6"),
            title_level=3,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Subnível 3"},
            position=Decimal("7"),
            title_level=2,
        )

        context = build_report_editor_context(self.report)
        outline = context["outline_tree"]

        self.assertEqual(len(outline), 3)
        self.assertEqual(outline[0].label, "Teste")
        self.assertEqual(outline[0].depth, 0)
        self.assertEqual(outline[1].label, "Seção um")
        self.assertEqual(len(outline[1].children), 2)
        self.assertEqual(outline[1].children[0].label, "Subseção 1.1")
        self.assertEqual(outline[1].children[0].depth, 1)
        self.assertEqual(outline[2].label, "Seção dois")
        self.assertEqual(len(outline[2].children), 2)
        self.assertEqual(outline[2].children[0].label, "Subnível 4")
        self.assertEqual(outline[2].children[1].label, "Subnível 3")

    def test_outline_heading_with_same_level_as_parent_is_root_sibling(self):
        """Garante título com mesmo title_level do ancestral como irmão na raiz visual."""
        root_heading = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Seção principal"},
            position=Decimal("1"),
            title_level=0,
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
            title_level=0,
        )

        context = build_report_editor_context(self.report)

        self.assertEqual(len(context["outline_tree"]), 2)
        self.assertEqual(context["outline_tree"][0].label, "Seção principal")
        self.assertEqual(context["outline_tree"][1].label, "Subseção")

    def test_outline_nests_heading_under_parent_when_title_level_is_deeper(self):
        """Garante aninhamento quando title_level indica subordinação ao título anterior."""
        root_heading = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Seção principal"},
            position=Decimal("1"),
            title_level=0,
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
            title_level=1,
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
