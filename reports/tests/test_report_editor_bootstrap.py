"""
Testes do bootstrap inicial do editor de relatório.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from reports.models import Report, ReportBlockType, ReportNode
from reports.services.report_editor_bootstrap import ensure_editor_bootstrap

User = get_user_model()


class ReportEditorBootstrapTests(TestCase):
    """Testes da criação automática do título H1 vazio."""

    @classmethod
    def setUpTestData(cls):
        """Prepara autor e relatório sem nós."""
        cls.author = User.objects.create_user(
            username="bootstrap_user",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Relatório vazio",
        )

    def test_bootstrap_creates_heading_node_when_empty(self):
        """Garante nó inicial heading nível 0 em relatório sem blocos."""
        node = ensure_editor_bootstrap(self.report)

        self.assertIsNotNone(node)
        self.assertEqual(self.report.nodes.count(), 1)
        self.assertEqual(node.block.block_type, ReportBlockType.HEADING)
        self.assertEqual(node.block.title_level, 0)
        self.assertEqual(node.block.content, {"text": ""})

    def test_bootstrap_is_idempotent_when_nodes_exist(self):
        """Garante que bootstrap não duplica nós quando árvore já possui conteúdo."""
        first = ensure_editor_bootstrap(self.report)
        second = ensure_editor_bootstrap(self.report)

        self.assertIsNone(second)
        self.assertEqual(self.report.nodes.count(), 1)
        self.assertEqual(first.pk, self.report.nodes.get().pk)
