"""Testes da API de configuração do laudo."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode, ReportUserConfig

User = get_user_model()


class ReportConfigApiViewTests(TestCase):
    """Testes dos endpoints GET/PATCH de configuração."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(
            username="config_api",
            password="senha-segura",
        )
        cls.report = Report.objects.create(author=cls.author, title="API config")

    def _patch_config(self, payload):
        self.client.login(username="config_api", password="senha-segura")
        return self.client.patch(
            reverse("reports:config", kwargs={"pk": self.report.pk}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_get_returns_report_config(self):
        """Garante leitura da configuração persistida do laudo."""
        self.client.login(username="config_api", password="senha-segura")
        response = self.client.get(
            reverse("reports:config", kwargs={"pk": self.report.pk}),
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["number_headings"])
        self.assertFalse(data["number_captions"])
        self.assertTrue(data["first_line_indent"])

    def test_patch_updates_report_and_user_defaults(self):
        """Garante persistência conjunta no laudo e nas preferências do usuário."""
        paragraph = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Corpo"},
            first_line_indent=True,
        )
        ReportNode.objects.create(
            report=self.report,
            block=paragraph,
            position=Decimal("1"),
        )

        response = self._patch_config(
            {
                "number_headings": False,
                "number_captions": True,
                "first_line_indent": False,
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["number_headings"])
        self.assertTrue(payload["number_captions"])
        self.assertFalse(payload["first_line_indent"])
        self.assertIn("outline_html", payload)
        self.assertIn("caption_numbers", payload)

        self.report.refresh_from_db()
        paragraph.refresh_from_db()
        user_config = ReportUserConfig.objects.get(user=self.author)

        self.assertFalse(self.report.number_headings)
        self.assertTrue(self.report.number_captions)
        self.assertFalse(self.report.first_line_indent)
        self.assertFalse(paragraph.first_line_indent)
        self.assertFalse(user_config.number_headings)
        self.assertTrue(user_config.number_captions)
        self.assertFalse(user_config.first_line_indent)
