"""
Testes dos filtros de template do sumário do editor.
"""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_editor_context import ReportOutlineEntry
from reports.templatetags.report_outline import outline_list_reorderable

User = get_user_model()


class OutlineListReorderableFilterTests(SimpleTestCase):
    """Testes do filtro que habilita arrastar e soltar no sumário."""

    def _entry(self, *, parent_id=None, label="Título"):
        return ReportOutlineEntry(
            node_id=uuid4(),
            label=label,
            title_level=0,
            depth=0,
            report_parent_id=parent_id,
        )

    def test_requires_at_least_two_entries(self):
        """Garante ausência de reordenação com menos de dois títulos."""
        self.assertFalse(outline_list_reorderable([self._entry()], ""))

    def test_requires_same_report_parent_id(self):
        """Garante ausência de reordenação quando irmãos visuais têm pais distintos."""
        parent_a = uuid4()
        parent_b = uuid4()
        entries = [
            self._entry(parent_id=parent_a, label="A"),
            self._entry(parent_id=parent_b, label="B"),
        ]
        self.assertFalse(outline_list_reorderable(entries, parent_a))

    def test_allows_reorder_for_direct_heading_siblings(self):
        """Garante reordenação quando todos compartilham o mesmo pai de nó."""
        parent_id = uuid4()
        entries = [
            self._entry(parent_id=parent_id, label="A"),
            self._entry(parent_id=parent_id, label="B"),
        ]
        self.assertTrue(outline_list_reorderable(entries, parent_id))


class OutlineEntryParentIdTests(TestCase):
    """Testes do identificador de pai real nos itens do sumário."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="outline_user",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="Sumário")

    def test_outline_entry_exposes_report_parent_id(self):
        """Garante que cada entrada do sumário traga o pai real do nó."""
        from reports.services.report_editor_context import build_report_editor_context

        parent_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Pai"},
        )
        parent_node = ReportNode.objects.create(
            report=self.report,
            block=parent_block,
            position=Decimal("1"),
        )
        child_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Filho"},
        )
        ReportNode.objects.create(
            report=self.report,
            parent=parent_node,
            block=child_block,
            position=Decimal("1"),
        )

        context = build_report_editor_context(self.report)
        child_entry = context["outline_tree"][0].children[0]

        self.assertEqual(child_entry.report_parent_id, parent_node.pk)
