# reportline/reports/tests/test_report_caption_text.py
"""
Testes da normalização de texto de legendas de imagem.
"""

from django.test import SimpleTestCase

from reports.services.report_caption_text import normalize_caption_text, strip_figure_prefix_from_caption


class ReportCaptionTextTests(SimpleTestCase):
    """Testes da remoção de prefixo Figura N em legendas."""

    def test_strip_figure_prefix_with_dash(self):
        """Garante remoção de prefixo Figura N com hífen."""
        self.assertEqual(
            strip_figure_prefix_from_caption("Figura 3 - Detalhe da fechadura."),
            "Detalhe da fechadura.",
        )

    def test_strip_figure_prefix_with_en_dash(self):
        """Garante remoção de prefixo com travessão."""
        self.assertEqual(
            strip_figure_prefix_from_caption("Figura 4 – Vista interna do ambiente."),
            "Vista interna do ambiente.",
        )

    def test_strip_figure_prefix_without_separator(self):
        """Garante remoção quando há apenas espaço após o número."""
        self.assertEqual(
            strip_figure_prefix_from_caption("Figura 2 Vista frontal do imóvel."),
            "Vista frontal do imóvel.",
        )

    def test_strip_figure_prefix_preserves_body_without_prefix(self):
        """Garante que legendas sem numeração permanecem intactas."""
        caption = "Vista frontal do imóvel, mostrando o portão metálico."
        self.assertEqual(normalize_caption_text(caption), caption)

    def test_strip_figure_prefix_handles_double_prefix(self):
        """Garante remoção iterativa quando a IA duplica o prefixo."""
        self.assertEqual(
            normalize_caption_text("Figura 3 - Figura 3 - Detalhe do vestígio."),
            "Detalhe do vestígio.",
        )
