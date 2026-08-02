"""Testes da API de layout de página do relatório."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_page_layout import HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT

User = get_user_model()


class ReportPageLayoutApiViewTests(TestCase):
    """Testes de PATCH do cabeçalho via API."""

    def setUp(self):
        self.user = User.objects.create_user(username="perito1", password="senha-segura")
        self.report = Report.objects.create(author=self.user, title="Laudo")
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.HEADING,
            content={"text": "Intro"},
        )
        ReportNode.objects.create(report=self.report, block=block, position=Decimal("1"))
        self.url = reverse("reports:page_layout", kwargs={"pk": self.report.pk})

    def _patch(self, payload):
        return self.client.patch(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_apply_template_enables_header(self):
        """Garante ativação de cabeçalho via apply_template."""
        self.client.force_login(self.user)
        response = self._patch(
            {
                "apply_template": True,
                "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertTrue(self.report.page_layout["header"]["enabled"])
        self.assertIn("html", response.json())

    def test_patch_header_text_cells(self):
        """Garante persistência de células de texto do cabeçalho."""
        self.client.force_login(self.user)
        self._patch(
            {
                "apply_template": True,
                "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
            }
        )

        response = self._patch(
            {
                "page_layout": {
                    "header": {
                        "enabled": True,
                        "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
                        "column_widths": [30, 70],
                        "cells": [
                            {
                                "type": "logo",
                                "logo_slot": "primary",
                                "file": "",
                                "image_id": "",
                                "width": 0,
                                "height": 0,
                                "alt": "",
                            },
                            {
                                "type": "text",
                                "text": "Instituição — Laudo",
                                "align": "left",
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(
            self.report.page_layout["header"]["cells"][1]["text"],
            "Instituição — Laudo",
        )

    def test_non_author_receives_404(self):
        """Garante bloqueio de alteração por usuário que não é autor."""
        other = User.objects.create_user(username="outro", password="senha-segura")
        self.client.force_login(other)
        response = self._patch(
            {
                "apply_template": True,
                "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
            }
        )
        self.assertEqual(response.status_code, 404)
