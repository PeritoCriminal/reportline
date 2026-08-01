"""
Testes da API JSON de nós do editor de relatório.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode

User = get_user_model()


class ReportNodeApiViewTests(TestCase):
    """Testes dos endpoints PATCH/POST de nós."""

    @classmethod
    def setUpTestData(cls):
        """Prepara relatório com título inicial."""
        cls.author = User.objects.create_user(
            username="api_user",
            password="senha-segura",
        )
        cls.other = User.objects.create_user(
            username="intruso",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="API")
        heading = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Intro"},
            title_level=0,
        )
        cls.node = ReportNode.objects.create(
            report=cls.report,
            block=heading,
            position=Decimal("1"),
        )

    def _patch_node(self, node, payload, user="api_user"):
        self.client.login(username=user, password="senha-segura")
        return self.client.patch(
            reverse(
                "reports:node_update",
                kwargs={"pk": self.report.pk, "node_id": node.pk},
            ),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _post_node(self, payload, user="api_user"):
        self.client.login(username=user, password="senha-segura")
        return self.client.post(
            reverse("reports:node_create", kwargs={"pk": self.report.pk}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _delete_node(self, node, user="api_user"):
        self.client.login(username=user, password="senha-segura")
        return self.client.delete(
            reverse(
                "reports:node_update",
                kwargs={"pk": self.report.pk, "node_id": node.pk},
            ),
        )

    def test_patch_updates_block_content(self):
        """Garante persistência de conteúdo via PATCH."""
        response = self._patch_node(self.node, {"content": {"text": "Atualizado"}})

        self.assertEqual(response.status_code, 200)
        self.node.block.refresh_from_db()
        self.assertEqual(self.node.block.content["text"], "Atualizado")

    def test_post_after_heading_creates_paragraph(self):
        """Garante parágrafo irmão após título via POST."""
        response = self._post_node({"after_node_id": str(self.node.pk)})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["block_type"], ReportBlockType.PARAGRAPH)
        self.assertIn("html", data)
        self.assertEqual(self.report.nodes.count(), 2)

    def test_post_heading_accepts_title_level(self):
        """Garante criação de título com nível hierárquico informado."""
        response = self._post_node(
            {
                "after_node_id": str(self.node.pk),
                "block_type": ReportBlockType.HEADING,
                "title_level": 2,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_type"], ReportBlockType.HEADING)
        self.assertEqual(payload["title_level"], 2)
        node = ReportNode.objects.get(pk=payload["node_id"])
        self.assertEqual(node.block.title_level, 2)

    def test_patch_converts_paragraph_to_heading_with_html(self):
        """Garante conversão de parágrafo em título via PATCH com HTML estrutural."""
        paragraph_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Texto convertido"},
        )
        paragraph_node = ReportNode.objects.create(
            report=self.report,
            block=paragraph_block,
            position=Decimal("2"),
        )

        response = self._patch_node(
            paragraph_node,
            {
                "content": {"text": "Texto convertido"},
                "block_type": ReportBlockType.HEADING,
                "title_level": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["block_type"], ReportBlockType.HEADING)
        self.assertEqual(payload["title_level"], 1)
        self.assertIn("html", payload)
        self.assertIn("report-editor-block-heading", payload["html"])
        paragraph_node.block.refresh_from_db()
        self.assertEqual(paragraph_node.block.block_type, ReportBlockType.HEADING)

    def test_non_author_post_receives_404(self):
        """Garante 404 para usuário que não é autor do relatório."""
        response = self._post_node(
            {"after_node_id": str(self.node.pk)},
            user="intruso",
        )
        self.assertEqual(response.status_code, 404)

    def test_append_list_item_via_patch(self):
        """Garante extensão de lista no mesmo nó."""
        list_block = ReportBlock.objects.create(
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": ["A"]},
        )
        list_node = ReportNode.objects.create(
            report=self.report,
            block=list_block,
            position=Decimal("2"),
        )

        response = self._patch_node(
            list_node,
            {"append_list_item": True, "items": ["A", "B"]},
        )

        self.assertEqual(response.status_code, 200)
        list_node.block.refresh_from_db()
        self.assertEqual(list_node.block.content["items"], ["A", "B", ""])
        self.assertEqual(response.json()["new_item_index"], 2)

    def test_post_after_image_sets_caption_paragraph(self):
        """Garante parágrafo de legenda após bloco de imagem."""
        image_block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content={"alt": "Foto", "file": ""},
        )
        image_node = ReportNode.objects.create(
            report=self.report,
            block=image_block,
            position=Decimal("3"),
        )

        response = self._post_node({"after_node_id": str(image_node.pk)})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["block_type"], ReportBlockType.PARAGRAPH)
        self.assertTrue(data["is_caption"])

    def test_post_before_node_inserts_sibling(self):
        """Garante inserção de irmão antes do nó de referência."""
        paragraph_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Corpo"},
        )
        paragraph_node = ReportNode.objects.create(
            report=self.report,
            block=paragraph_block,
            position=Decimal("2"),
        )

        response = self._post_node({"before_node_id": str(paragraph_node.pk)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["insertion"], "before")
        self.assertEqual(self.report.nodes.count(), 3)

    def test_delete_node_via_api(self):
        """Garante exclusão de nó via DELETE."""
        paragraph_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": ""},
        )
        paragraph_node = ReportNode.objects.create(
            report=self.report,
            block=paragraph_block,
            position=Decimal("2"),
        )

        response = self._delete_node(paragraph_node)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReportNode.objects.filter(pk=paragraph_node.pk).exists())

    def test_delete_only_node_returns_bad_request(self):
        """Garante erro ao excluir único nó do relatório."""
        single_report = Report.objects.create(author=self.author, title="Único")
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Só"},
        )
        node = ReportNode.objects.create(
            report=single_report,
            block=block,
            position=Decimal("1"),
        )

        self.client.login(username="api_user", password="senha-segura")
        response = self.client.delete(
            reverse(
                "reports:node_update",
                kwargs={"pk": single_report.pk, "node_id": node.pk},
            ),
        )

        self.assertEqual(response.status_code, 400)

    def _post_reorder(self, payload, user="api_user"):
        self.client.login(username=user, password="senha-segura")
        return self.client.post(
            reverse("reports:node_reorder", kwargs={"pk": self.report.pk}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_reorder_nodes_updates_heading_order(self):
        """Garante reordenação de títulos raiz via POST JSON."""
        second_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Final"},
            title_level=0,
        )
        second_node = ReportNode.objects.create(
            report=self.report,
            block=second_block,
            position=Decimal("2"),
        )

        response = self._post_reorder(
            {
                "parent_node_id": None,
                "ordered_node_ids": [str(second_node.pk), str(self.node.pk)],
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.node.refresh_from_db()
        second_node.refresh_from_db()
        self.assertGreater(self.node.position, second_node.position)

    def test_reorder_nodes_rejects_foreign_author(self):
        """Garante bloqueio de reordenação por usuário que não é autor."""
        second_block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Final"},
        )
        second_node = ReportNode.objects.create(
            report=self.report,
            block=second_block,
            position=Decimal("2"),
        )

        response = self._post_reorder(
            {
                "parent_node_id": None,
                "ordered_node_ids": [str(second_node.pk), str(self.node.pk)],
            },
            user="intruso",
        )

        self.assertEqual(response.status_code, 404)
