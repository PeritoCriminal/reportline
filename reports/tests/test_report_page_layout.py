"""Testes de layout de página (cabeçalho) do relatório."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.services.report_page_layout import (
    HEADER_LOGO_INITIAL_HEIGHT_PX,
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    HEADER_TEMPLATE_LOGO_TEXT_LOGO,
    apply_header_template,
    build_header_cells_for_template,
    default_page_layout,
    initial_header_logo_display_size,
    normalize_page_layout,
    update_logo_cell_from_image,
)


class ReportPageLayoutTests(TestCase):
    """Testes de normalização e modelos de cabeçalho."""

    def test_default_page_layout_has_header_disabled(self):
        """Garante layout inicial sem cabeçalho ativo."""
        layout = default_page_layout()
        self.assertFalse(layout["header"]["enabled"])
        self.assertEqual(layout["header"]["cells"], [])

    def test_apply_header_template_logo_left_text_right(self):
        """Garante modelo com logo à esquerda e texto à direita."""
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        header = layout["header"]

        self.assertTrue(header["enabled"])
        self.assertEqual(header["template_id"], HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        self.assertEqual(len(header["cells"]), 2)
        self.assertEqual(header["cells"][0]["type"], "logo")
        self.assertEqual(header["cells"][1]["type"], "text")

    def test_apply_header_template_logo_text_logo(self):
        """Garante modelo com duas logos e texto central."""
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_TEXT_LOGO)
        header = layout["header"]

        self.assertEqual(len(header["cells"]), 3)
        self.assertEqual(header["cells"][0]["logo_slot"], "primary")
        self.assertEqual(header["cells"][2]["logo_slot"], "secondary")

    def test_build_header_cells_preserves_logo_on_template_change(self):
        """Garante preservação de logo compatível ao trocar modelo."""
        initial = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        initial["header"]["cells"][0]["file"] = "reports/x/logo.png"
        initial["header"]["cells"][0]["image_id"] = "abc"

        cells = build_header_cells_for_template(
            HEADER_TEMPLATE_LOGO_TEXT_LOGO,
            existing_cells=initial["header"]["cells"],
        )

        self.assertEqual(cells[0]["file"], "reports/x/logo.png")
        self.assertEqual(cells[0]["image_id"], "abc")

    def test_update_logo_cell_from_image(self):
        """Garante atualização de célula de logo após upload."""
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        updated = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": "reports/1/img.jpg",
                "image_id": "uuid-1",
                "width": 1200,
                "height": 800,
                "alt": "",
            },
        )

        logo_cell = updated["header"]["cells"][0]
        self.assertEqual(logo_cell["file"], "reports/1/img.jpg")
        self.assertEqual(logo_cell["height"], HEADER_LOGO_INITIAL_HEIGHT_PX)
        self.assertEqual(
            logo_cell["width"],
            initial_header_logo_display_size(1200, 800)[0],
        )

    def test_initial_header_logo_display_size_preserves_aspect_ratio(self):
        """Garante altura inicial fixa de 3 cm com largura proporcional."""
        width, height = initial_header_logo_display_size(400, 200)
        self.assertEqual(height, HEADER_LOGO_INITIAL_HEIGHT_PX)
        self.assertEqual(width, HEADER_LOGO_INITIAL_HEIGHT_PX * 2)

    def test_normalize_rejects_invalid_template(self):
        """Garante rejeição de modelo de cabeçalho inválido."""
        with self.assertRaises(ValidationError):
            apply_header_template(None, "invalid")

    def test_normalize_disabled_header_clears_cells(self):
        """Garante cabeçalho desativado sem células persistidas."""
        normalized = normalize_page_layout(
            {
                "header": {
                    "enabled": False,
                    "template_id": HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
                    "cells": [{"type": "text", "text": "X"}],
                }
            }
        )
        self.assertFalse(normalized["header"]["enabled"])
        self.assertEqual(normalized["header"]["cells"], [])
