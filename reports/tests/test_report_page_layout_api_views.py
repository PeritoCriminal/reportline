"""Testes da API de layout de página do relatório."""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    FOOTER_TEMPLATE_LOGO_TEXT_LOGO,
    FOOTER_TEMPLATE_TEXT_ONLY,
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
)

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
        payload = response.json()
        self.assertIn("html", payload)
        self.assertIn("header_html", payload)
        self.assertIn("footer_html", payload)

    def test_apply_footer_template_enables_footer(self):
        """Garante ativação de rodapé via apply_template com section footer."""
        self.client.force_login(self.user)
        response = self._patch(
            {
                "apply_template": True,
                "template_id": FOOTER_TEMPLATE_TEXT_ONLY,
                "section": "footer",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertTrue(self.report.page_layout["footer"]["enabled"])
        self.assertIn("footer_html", response.json())

    def test_patch_header_preserves_footer(self):
        """Garante que PATCH parcial do cabeçalho não desativa rodapé existente."""
        self.client.force_login(self.user)
        self._patch(
            {
                "apply_template": True,
                "template_id": FOOTER_TEMPLATE_TEXT_ONLY,
                "section": "footer",
            }
        )
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
                                "text": "Cabeçalho",
                                "align": "left",
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertTrue(self.report.page_layout["footer"]["enabled"])
        self.assertEqual(
            self.report.page_layout["header"]["cells"][1]["text"],
            "Cabeçalho",
        )

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

    def test_patch_header_text_cell_indent(self):
        """Garante persistência de recuo em células de texto do cabeçalho via API."""
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
                        "column_widths": [1, 99],
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
                                "text": "Instituição",
                                "align": "left",
                                "indent_level": 2,
                                "first_line_indent": True,
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        text_cell = self.report.page_layout["header"]["cells"][1]
        self.assertEqual(text_cell["indent_level"], 2)
        self.assertTrue(text_cell["first_line_indent"])
        self.assertIn('data-indent-level="2"', response.json()["header_html"])
        self.assertIn('data-first-line-indent="true"', response.json()["header_html"])

    def test_patch_footer_text_cell_page_number_disabled(self):
        """Garante remoção da numeração de páginas no rodapé via API."""
        self.client.force_login(self.user)
        self._patch(
            {
                "apply_template": True,
                "template_id": FOOTER_TEMPLATE_TEXT_ONLY,
                "section": "footer",
            }
        )

        response = self._patch(
            {
                "page_layout": {
                    "footer": {
                        "enabled": True,
                        "template_id": FOOTER_TEMPLATE_TEXT_ONLY,
                        "column_widths": [100],
                        "cells": [
                            {
                                "type": "text",
                                "text": "Instituição",
                                "align": "center",
                                "indent_level": 0,
                                "first_line_indent": False,
                                "show_page_number": False,
                            },
                        ],
                    }
                }
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertFalse(self.report.page_layout["footer"]["cells"][0]["show_page_number"])
        footer_html = response.json()["footer_html"]
        self.assertIn('data-show-page-number="false"', footer_html)
        self.assertNotIn("data-report-page-number-current", footer_html)

    def test_clear_header_logo_cell_via_api_removes_image(self):
        """Garante exclusão de logo do cabeçalho via API e limpeza do media."""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from reports.models import ReportImage
        from reports.services.report_image_upload import build_image_block_content, store_report_image

        self.client.force_login(self.user)
        self._patch(
            {
                "apply_template": True,
                "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
            }
        )

        buffer = BytesIO()
        Image.new("RGB", (200, 100), color="orange").save(buffer, format="JPEG")
        buffer.seek(0)
        upload = SimpleUploadedFile("logo.jpg", buffer.read(), content_type="image/jpeg")
        report_image = store_report_image(self.report, upload)
        image_content = build_image_block_content(report_image)

        self._patch(
            {
                "update_logo_cell": 0,
                "section": "header",
                "image": image_content,
            }
        )

        image_id = report_image.pk
        response = self._patch(
            {
                "clear_logo_cell": 0,
                "section": "header",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.report.refresh_from_db()
        self.assertEqual(self.report.page_layout["header"]["cells"][0]["image_id"], "")
        self.assertFalse(ReportImage.objects.filter(pk=image_id).exists())
        self.assertNotIn("has-image", response.json()["header_html"])

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
