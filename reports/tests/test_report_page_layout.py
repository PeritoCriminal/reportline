# reportline/reports/tests/test_report_page_layout.py
"""Testes de layout de página (cabeçalho e rodapé) do relatório."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from reports.services.report_kind import merge_reportline_meta
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    FOOTER_TEMPLATE_LOGO_TEXT_LOGO,
    FOOTER_TEMPLATE_TEXT_ONLY,
    HEADER_EXTRA_ROW_TYPE_RULE,
    HEADER_LOGO_INITIAL_HEIGHT_PX,
    HEADER_LOGO_INITIAL_WIDTH_PX,
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    HEADER_TEMPLATE_LOGO_TEXT_LOGO,
    MAX_HEADER_EXTRA_ROWS,
    apply_footer_template,
    apply_header_template,
    build_footer_cells_for_template,
    build_header_cells_for_template,
    default_header_extra_rule_row,
    default_header_extra_text_row,
    default_page_layout,
    initial_header_logo_display_size,
    initial_header_logo_display_size_by_width,
    clamp_header_logo_display_size_by_width,
    logo_display_size_style,
    prepare_logo_cell_for_document,
    merge_page_layout,
    normalize_header_extra_rows,
    normalize_page_layout,
    update_footer_logo_cell_from_image,
    update_logo_cell_from_image,
)


class ReportPageLayoutTests(TestCase):
    """Testes de normalização e modelos de cabeçalho."""

    def test_default_page_layout_has_header_disabled(self):
        """Garante layout inicial sem cabeçalho nem rodapé ativos."""
        layout = default_page_layout()
        self.assertFalse(layout["header"]["enabled"])
        self.assertEqual(layout["header"]["cells"], [])
        self.assertEqual(layout["header"]["extra_rows"], [])
        self.assertFalse(layout["footer"]["enabled"])
        self.assertEqual(layout["footer"]["cells"], [])

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

    def test_initial_header_logo_display_size_by_width_preserves_aspect_ratio(self):
        """Garante largura inicial fixa de 1,5 cm com altura proporcional."""
        width, height = initial_header_logo_display_size_by_width(400, 200)
        self.assertEqual(width, HEADER_LOGO_INITIAL_WIDTH_PX)
        self.assertEqual(height, HEADER_LOGO_INITIAL_WIDTH_PX // 2)

    def test_update_logo_cell_honors_display_size_override(self):
        """Garante uso de dimensões de exibição explícitas quando informadas."""
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        updated = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": "reports/1/img.jpg",
                "image_id": "uuid-1",
                "width": 1200,
                "height": 800,
                "display_width": 50,
                "display_height": 25,
                "alt": "",
            },
        )

        logo_cell = updated["header"]["cells"][0]
        self.assertEqual(logo_cell["width"], 50)
        self.assertEqual(logo_cell["height"], 25)

    def test_logo_display_size_style_uses_physical_cm_units(self):
        """Garante CSS inline em cm para escala correta no preview A4."""
        style = logo_display_size_style(HEADER_LOGO_INITIAL_WIDTH_PX, 47)
        self.assertIn("width: 1.51cm", style)
        self.assertIn("height:", style)
        self.assertNotIn("px", style)

    def test_clamp_header_logo_display_size_by_width_scales_oversized_logos(self):
        """Garante redução proporcional de logos acima de 1,5 cm de largura."""
        width, height = clamp_header_logo_display_size_by_width(400, 200)
        self.assertEqual(width, HEADER_LOGO_INITIAL_WIDTH_PX)
        self.assertEqual(height, HEADER_LOGO_INITIAL_WIDTH_PX // 2)

    def test_prepare_logo_cell_for_document_clamps_forensic_header_logos(self):
        """Garante limite institucional de largura em laudos periciais na leitura."""
        page_layout = merge_reportline_meta({}, workflow="generic")
        prepared = prepare_logo_cell_for_document(
            {
                "type": "logo",
                "file": "reports/1/logo.png",
                "width": 400,
                "height": 200,
            },
            page_layout,
            band="header",
        )
        self.assertEqual(prepared["width"], HEADER_LOGO_INITIAL_WIDTH_PX)
        self.assertIn("display_size_style", prepared)
        self.assertIn("cm", prepared["display_size_style"])

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
        self.assertEqual(normalized["header"]["extra_rows"], [])

    def test_normalize_header_extra_rows_text_and_rule(self):
        """Garante normalização de linhas extras de texto e horizontal."""
        rows = normalize_header_extra_rows(
            [
                default_header_extra_rule_row(),
                default_header_extra_text_row(align="right", muted=True),
            ]
        )
        self.assertEqual(rows[0]["type"], HEADER_EXTRA_ROW_TYPE_RULE)
        self.assertEqual(rows[1]["align"], "right")
        self.assertTrue(rows[1]["muted"])

    def test_normalize_header_extra_rows_respects_limit(self):
        """Garante limite máximo de linhas extras no cabeçalho."""
        too_many = [default_header_extra_rule_row() for _ in range(MAX_HEADER_EXTRA_ROWS + 1)]
        with self.assertRaises(ValidationError):
            normalize_header_extra_rows(too_many)

    def test_apply_header_template_preserves_extra_rows(self):
        """Garante preservação de linhas extras ao trocar modelo do cabeçalho."""
        layout = apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout["header"]["extra_rows"] = [
            default_header_extra_rule_row(),
            default_header_extra_text_row(align="right", muted=True),
        ]
        updated = apply_header_template(layout, HEADER_TEMPLATE_LOGO_TEXT_LOGO)
        self.assertEqual(len(updated["header"]["extra_rows"]), 2)
        self.assertTrue(updated["header"]["extra_rows"][1]["muted"])

    def test_apply_footer_template_text_only(self):
        """Garante modelo de rodapé apenas com texto e numeração."""
        layout = apply_footer_template(None, FOOTER_TEMPLATE_TEXT_ONLY)
        footer = layout["footer"]

        self.assertTrue(footer["enabled"])
        self.assertEqual(footer["template_id"], FOOTER_TEMPLATE_TEXT_ONLY)
        self.assertEqual(len(footer["cells"]), 1)
        self.assertEqual(footer["cells"][0]["type"], "text")
        self.assertTrue(footer["cells"][0]["show_page_number"])

    def test_apply_footer_template_logo_left_text_right(self):
        """Garante modelo de rodapé com imagem à esquerda e texto à direita."""
        layout = apply_footer_template(None, FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        footer = layout["footer"]

        self.assertEqual(len(footer["cells"]), 2)
        self.assertEqual(footer["cells"][0]["type"], "logo")
        self.assertEqual(footer["cells"][1]["type"], "text")
        self.assertTrue(footer["cells"][1]["show_page_number"])

    def test_build_footer_cells_preserves_text_on_template_change(self):
        """Garante preservação de texto compatível ao trocar modelo de rodapé."""
        initial = apply_footer_template(None, FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        initial["footer"]["cells"][1]["text"] = "Instituição — Contato"

        cells = build_footer_cells_for_template(
            FOOTER_TEMPLATE_LOGO_TEXT_LOGO,
            existing_cells=initial["footer"]["cells"],
        )

        self.assertEqual(cells[1]["text"], "Instituição — Contato")
        self.assertTrue(cells[1]["show_page_number"])

    def test_update_footer_logo_cell_from_image(self):
        """Garante atualização de célula de logo do rodapé após upload."""
        layout = apply_footer_template(None, FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        updated = update_footer_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": "reports/1/footer.jpg",
                "image_id": "uuid-2",
                "width": 600,
                "height": 400,
                "alt": "",
            },
        )

        logo_cell = updated["footer"]["cells"][0]
        self.assertEqual(logo_cell["file"], "reports/1/footer.jpg")
        self.assertEqual(logo_cell["height"], HEADER_LOGO_INITIAL_HEIGHT_PX)

    def test_merge_page_layout_preserves_unsent_band(self):
        """Garante que atualização parcial preserve faixa não enviada."""
        layout = apply_footer_template(None, FOOTER_TEMPLATE_TEXT_ONLY)
        layout["footer"]["cells"][0]["text"] = "Rodapé fixo"

        merged = merge_page_layout(
            layout,
            {
                "header": apply_header_template(None, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)["header"],
            },
        )

        self.assertTrue(merged["header"]["enabled"])
        self.assertTrue(merged["footer"]["enabled"])
        self.assertEqual(merged["footer"]["cells"][0]["text"], "Rodapé fixo")

    def test_normalize_text_cell_includes_indent_fields(self):
        """Garante persistência de recuo em células de texto do cabeçalho."""
        from reports.services.report_page_layout import normalize_text_cell

        normalized = normalize_text_cell(
            {
                "type": "text",
                "text": "Texto",
                "align": "left",
                "indent_level": 2,
                "first_line_indent": True,
            }
        )
        self.assertEqual(normalized["indent_level"], 2)
        self.assertTrue(normalized["first_line_indent"])

    def test_footer_text_cell_shows_page_number(self):
        """Garante helper de numeração respeita flag desativada."""
        from reports.services.report_page_layout import footer_text_cell_shows_page_number

        self.assertTrue(
            footer_text_cell_shows_page_number({"type": "text", "show_page_number": True})
        )
        self.assertFalse(
            footer_text_cell_shows_page_number({"type": "text", "show_page_number": False})
        )
        self.assertFalse(footer_text_cell_shows_page_number({"type": "logo"}))

    def test_normalize_footer_text_cell_respects_disabled_page_number(self):
        """Garante persistência de show_page_number=false no rodapé."""
        from reports.services.report_page_layout import normalize_footer_text_cell

        normalized = normalize_footer_text_cell(
            {
                "type": "text",
                "text": "Contato",
                "align": "center",
                "show_page_number": False,
            }
        )
        self.assertFalse(normalized["show_page_number"])

    def test_normalize_rejects_invalid_footer_template(self):
        """Garante rejeição de modelo de rodapé inválido."""
        with self.assertRaises(ValidationError):
            apply_footer_template(None, "invalid")
