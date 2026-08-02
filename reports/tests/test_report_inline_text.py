"""Testes de sanitização de HTML inline em campos de texto."""

from django.test import TestCase

from reports.services.report_inline_text import (
    inline_text_plain,
    sanitize_header_text_html,
    sanitize_inline_text_html,
)


class ReportInlineTextTests(TestCase):
    """Testes de sanitização e extração de texto inline."""

    def test_plain_text_preserved_without_tags(self):
        """Garante que texto sem markup permanece inalterado."""
        self.assertEqual(sanitize_inline_text_html("Laudo pericial"), "Laudo pericial")

    def test_allowed_formatting_tags_preserved(self):
        """Garante preservação de negrito, itálico, sublinhado e riscado."""
        html = "<strong>N</strong><em>I</em><u>S</u><s>R</s>"
        sanitized = sanitize_inline_text_html(html)
        self.assertIn("<strong>N</strong>", sanitized)
        self.assertIn("<em>I</em>", sanitized)
        self.assertIn("<u>S</u>", sanitized)
        self.assertIn("<s>R</s>", sanitized)

    def test_script_tags_removed(self):
        """Garante remoção de scripts maliciosos mantendo texto visível."""
        sanitized = sanitize_inline_text_html('<script>alert("x")</script>Texto')
        self.assertNotIn("script", sanitized)
        self.assertIn("Texto", sanitized)

    def test_alias_tags_normalized(self):
        """Garante normalização de tags legadas para equivalentes semânticos."""
        sanitized = sanitize_inline_text_html("<b>negrito</b> <i>itálico</i>")
        self.assertEqual(sanitized, "<strong>negrito</strong> <em>itálico</em>")

    def test_inline_text_plain_strips_markup(self):
        """Garante extração de texto puro para sumário e rótulos."""
        plain = inline_text_plain("<strong>Título</strong> do laudo")
        self.assertEqual(plain, "Título do laudo")

    def test_inline_link_preserved_with_safe_href(self):
        """Garante preservação de link inline com URL segura."""
        sanitized = sanitize_inline_text_html(
            '<a href="https://exemplo.gov.br">Portal</a>'
        )
        self.assertEqual(
            sanitized,
            '<a href="https://exemplo.gov.br">Portal</a>',
        )

    def test_inline_link_without_scheme_gets_https(self):
        """Garante normalização de URL sem esquema para https."""
        sanitized = sanitize_inline_text_html(
            '<a href="exemplo.gov.br">Portal</a>'
        )
        self.assertIn('href="https://exemplo.gov.br"', sanitized)

    def test_javascript_link_is_stripped(self):
        """Garante remoção de links com esquema perigoso."""
        sanitized = sanitize_inline_text_html(
            '<a href="javascript:alert(1)">Ataque</a>'
        )
        self.assertNotIn("<a ", sanitized)
        self.assertIn("Ataque", sanitized)


class SanitizeHeaderTextHtmlTests(TestCase):
    """Testes de sanitização de HTML de célula de cabeçalho."""

    def test_preserves_line_breaks(self):
        """Garante que quebras de linha ``<br>`` sejam preservadas."""
        result = sanitize_header_text_html("Linha 1<br>Linha 2")
        self.assertEqual(result, "Linha 1<br>Linha 2")

    def test_converts_paragraphs_to_line_breaks(self):
        """Garante normalização de parágrafos HTML em quebras de linha."""
        result = sanitize_header_text_html("<p>Primeira</p><p>Segunda</p>")
        self.assertEqual(result, "Primeira<br>Segunda")

    def test_preserves_inline_formatting(self):
        """Garante negrito e itálico junto com quebras de linha."""
        result = sanitize_header_text_html("<strong>Título</strong><br><em>Sub</em>")
        self.assertEqual(result, "<strong>Título</strong><br><em>Sub</em>")

    def test_strips_dangerous_tags(self):
        """Garante remoção de tags não permitidas no cabeçalho."""
        result = sanitize_header_text_html("<script>x</script>Texto")
        self.assertNotIn("script", result)
        self.assertIn("Texto", result)

    def test_inline_sanitizer_still_strips_br(self):
        """Garante que sanitização inline comum não preserve quebras de linha."""
        result = sanitize_inline_text_html("A<br>B")
        self.assertEqual(result, "AB")
