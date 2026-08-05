"""
Testes do serviço de contexto de renderização de documento.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_document_context import (
    build_report_document_context,
    load_report_document_script,
    load_report_document_styles,
)
from reports.services.report_page_layout import (
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
    apply_header_template,
    update_logo_cell_from_image,
)

User = get_user_model()


class ReportDocumentContextTests(TestCase):
    """Testes da montagem de seções para leitura do relatório."""

    @classmethod
    def setUpTestData(cls):
        """Prepara autor e relatório base para cenários de documento."""
        cls.author = User.objects.create_user(
            username="document_reader",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Laudo de leitura",
        )
        cls.factory = RequestFactory()

    def _request(self):
        """Cria requisição HTTP simulada para resolução de URLs absolutas."""
        return self.factory.get("/reports/preview/")

    def _create_node(
        self,
        block_type,
        content,
        parent=None,
        position=Decimal("0"),
        title_level=0,
    ):
        """Cria nó com bloco genérico para cenários de teste."""
        block = ReportBlock.objects.create(
            block_type=block_type,
            content=content,
            title_level=title_level,
        )
        return ReportNode.objects.create(
            report=self.report,
            parent=parent,
            block=block,
            position=position,
        )

    def test_sections_follow_body_entries_reading_order(self):
        """Garante ordem de seções idêntica à sequência profundidade-primeiro do corpo."""
        first = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Parte 1"},
            position=Decimal("1"),
        )
        second = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Detalhe."},
            parent=first,
            position=Decimal("1"),
        )
        third = self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": "Encerramento."},
            position=Decimal("2"),
        )

        context = build_report_document_context(self.report, self._request())
        node_ids = [section.node_id for section in context["sections"]]

        self.assertEqual(node_ids, [first.pk, second.pk, third.pk])

    def test_body_html_sanitizes_dangerous_markup(self):
        """Garante remoção de scripts maliciosos no HTML de leitura."""
        self._create_node(
            ReportBlockType.PARAGRAPH,
            {"text": '<script>alert("x")</script>Texto seguro'},
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]

        self.assertNotIn("script", section.body_html)
        self.assertIn("Texto seguro", section.body_html)

    def test_body_html_preserves_allowed_inline_formatting(self):
        """Garante preservação de formatação inline permitida em títulos."""
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "<strong>Introdução</strong>"},
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]

        self.assertEqual(section.body_html, "<strong>Introdução</strong>")

    def test_heading_number_propagated_to_sections(self):
        """Garante numeração automática de títulos nas seções de leitura."""
        first = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Introdução"},
            position=Decimal("1"),
            title_level=0,
        )
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Detalhe"},
            parent=first,
            position=Decimal("1"),
            title_level=1,
        )

        context = build_report_document_context(self.report, self._request())
        numbers = [section.heading_number for section in context["sections"]]

        self.assertEqual(numbers, ["", "1.1"])

    def test_caption_number_propagated_to_sections(self):
        """Garante numeração de legendas quando configuração está ativa."""
        self.report.number_captions = True
        self.report.save(update_fields=["number_captions"])

        image_block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content={"alt": "Foto", "file": "reports/images/sample.jpg", "width": 100, "height": 80},
        )
        ReportNode.objects.create(
            report=self.report,
            block=image_block,
            position=Decimal("1"),
        )
        caption_block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Legenda da figura"},
            first_line_indent=False,
        )
        caption_node = ReportNode.objects.create(
            report=self.report,
            block=caption_block,
            position=Decimal("2"),
        )

        context = build_report_document_context(self.report, self._request())
        caption_section = next(
            section for section in context["sections"] if section.node_id == caption_node.pk
        )

        self.assertTrue(caption_section.is_caption)
        self.assertEqual(caption_section.caption_number, 1)
        self.assertEqual(caption_section.body_html, "Legenda da figura")

    def test_table_content_enriched_in_sections(self):
        """Garante células de tabela sanitizadas e metadados estruturais preservados."""
        self._create_node(
            ReportBlockType.TABLE,
            {
                "headers": ["<strong>Coluna</strong>"],
                "rows": [["<em>Valor</em>"]],
                "show_borders": True,
                "show_header": True,
                "column_widths": [100],
            },
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]

        self.assertEqual(section.block_type, ReportBlockType.TABLE)
        self.assertEqual(section.content["headers"][0]["text"], "<strong>Coluna</strong>")
        self.assertEqual(section.content["rows"][0][0]["text"], "<em>Valor</em>")
        self.assertEqual(section.content["column_widths"], [100.0])

    def test_table_without_headers_preserves_column_widths_in_document(self):
        """Garante larguras de coluna no preview quando a tabela não tem cabeçalho."""
        self._create_node(
            ReportBlockType.TABLE,
            {
                "headers": [],
                "rows": [
                    [
                        {"type": "text", "text": "QR", "align": "center"},
                        {
                            "type": "text",
                            "text": '<a href="https://maps.google.com">Maps</a>',
                            "align": "left",
                        },
                    ]
                ],
                "show_borders": True,
                "show_header": False,
                "column_widths": [28, 72],
                "display_width": 100,
            },
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]

        self.assertEqual(section.content["column_widths"], [28, 72])
        link_html = section.content["rows"][0][1]["text"]
        self.assertIn('target="_blank"', link_html)
        self.assertIn('rel="noopener noreferrer"', link_html)

    def test_table_image_cell_dimensions_preserved_in_document(self):
        """Garante dimensões editadas da imagem na célula refletidas no preview."""
        self._create_node(
            ReportBlockType.TABLE,
            {
                "headers": [],
                "rows": [
                    [
                        {
                            "type": "image",
                            "alt": "QR",
                            "file": "reports/images/qr.png",
                            "image_id": "",
                            "width": 80,
                            "height": 80,
                            "align": "center",
                        },
                        {"type": "text", "text": "Endereço editado", "align": "left"},
                    ]
                ],
                "show_borders": False,
                "show_header": False,
                "column_widths": [22, 78],
                "display_width": 100,
            },
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]
        image_cell = section.content["rows"][0][0]

        self.assertEqual(image_cell["width"], 80)
        self.assertEqual(image_cell["height"], 80)
        self.assertEqual(section.content["rows"][0][1]["text"], "Endereço editado")
        self.assertFalse(section.content["show_borders"])

    def test_table_text_cell_soft_breaks_preserved_in_document(self):
        """Garante quebras Shift+Enter na célula apareçam no preview."""
        self._create_node(
            ReportBlockType.TABLE,
            {
                "headers": [],
                "rows": [
                    [
                        {"type": "text", "text": "", "align": "center"},
                        {
                            "type": "text",
                            "text": "<strong>Endereço:</strong><br>Rua A<br>Rua B",
                            "align": "left",
                        },
                    ]
                ],
                "show_borders": False,
                "show_header": False,
                "column_widths": [22, 78],
            },
            position=Decimal("2"),
        )

        context = build_report_document_context(self.report, self._request())
        section = next(
            item for item in context["sections"] if item.block_type == ReportBlockType.TABLE
        )
        text_html = section.content["rows"][0][1]["text"]
        self.assertIn("<br>", text_html)
        self.assertIn("Rua A", text_html)
        self.assertIn("Rua B", text_html)

    def test_image_figures_use_absolute_url(self):
        """Garante URL absoluta de imagem para consumo externo (preview/PDF)."""
        self._create_node(
            ReportBlockType.IMAGE,
            {
                "alt": "Diagrama",
                "file": "reports/images/diagram.png",
                "width": 320,
                "height": 240,
            },
            position=Decimal("1"),
        )

        request = self._request()
        context = build_report_document_context(self.report, request)
        section = context["sections"][0]

        self.assertEqual(len(section.figures), 1)
        self.assertTrue(section.figures[0]["url"].startswith("http://testserver/"))
        self.assertIn("reports/images/diagram.png", section.figures[0]["url"])
        self.assertEqual(section.content["url"], section.figures[0]["url"])
        self.assertEqual(section.figures[0]["alt"], "Diagrama")

    def test_list_items_html_sanitized_in_sections(self):
        """Garante itens de lista com HTML inline sanitizado."""
        self._create_node(
            ReportBlockType.UNORDERED_LIST,
            {"items": ["<strong>Primeiro</strong>", '<script>x</script>Segundo']},
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        section = context["sections"][0]

        self.assertEqual(section.list_items_html[0], "<strong>Primeiro</strong>")
        self.assertNotIn("script", section.list_items_html[1])
        self.assertIn("Segundo", section.list_items_html[1])

    def test_empty_report_returns_empty_sections(self):
        """Garante seções vazias quando relatório não possui blocos."""
        empty_report = Report.objects.create(
            author=self.author,
            title="Vazio",
        )

        context = build_report_document_context(empty_report, self._request())

        self.assertEqual(context["sections"], [])
        self.assertEqual(context["report"], empty_report)

    def test_section_primary_key_is_uuid(self):
        """Garante identificador UUID estável nas seções para âncoras de bloco."""
        node = self._create_node(
            ReportBlockType.HEADING,
            {"text": "Capítulo"},
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())

        self.assertIsInstance(context["sections"][0].node_id, uuid.UUID)
        self.assertEqual(context["sections"][0].node_id, node.pk)

    def test_document_styles_loaded_from_static_css(self):
        """Garante CSS de leitura embutível a partir do arquivo estático."""
        styles = load_report_document_styles()

        self.assertIn(".report-document {", styles)
        self.assertIn("Arial", styles)
        self.assertIn("@page", styles)
        self.assertIn("size: A4 portrait", styles)
        self.assertIn("12pt", styles)

    def test_document_styles_follow_abnt_page_margins(self):
        """Garante margens assimétricas ABNT (3cm sup./esq.; 2cm inf./dir.) no CSS."""
        styles = load_report_document_styles()

        self.assertIn("margin: 3cm 2cm 2cm 3cm", styles)
        self.assertIn("--report-document-page-margin-top: 3cm", styles)
        self.assertIn("--report-document-page-margin-left: 3cm", styles)
        self.assertIn("--report-document-page-margin-bottom: 2cm", styles)
        self.assertIn("--report-document-page-margin-right: 2cm", styles)

    def test_build_context_includes_document_styles(self):
        """Garante contexto completo com estilos inline para o template do documento."""
        context = build_report_document_context(self.report, self._request())

        self.assertIn(".report-document {", context["document_styles"])

    def test_document_styles_include_orphan_widow_control(self):
        """Garante controle tipográfico de linhas órfãs e viúvas em parágrafos."""
        styles = load_report_document_styles()

        self.assertIn("orphans: 2", styles)
        self.assertIn("widows: 2", styles)
        self.assertIn("hyphens: none", styles)
        self.assertIn("word-break: normal", styles)
        self.assertIn("report-document-block--continued", styles)

    def test_document_script_splits_paragraphs_on_visual_line_boundaries(self):
        """Garante paginação por linhas visuais com mínimo de linhas por fragmento."""
        script = load_report_document_script()

        self.assertIn("getVisualLineStartOffsets", script)
        self.assertIn("MIN_FRAGMENT_LINES", script)
        self.assertNotIn("findSplitOffsetForOrphansWidows", script)

    def test_document_script_splits_lists_with_minimum_items_per_fragment(self):
        """Garante paginação de listas por itens e linhas com mínimo por fragmento."""
        script = load_report_document_script()

        self.assertIn("splitListBlock", script)
        self.assertIn("splitListBlockByItems", script)
        self.assertIn("splitLastListItemByLines", script)
        self.assertIn("MIN_FRAGMENT_ITEMS", script)
        self.assertIn('setAttribute("start"', script)

    def test_document_styles_include_list_orphan_widow_control(self):
        """Garante controle tipográfico de linhas órfãs e viúvas em itens de lista."""
        styles = load_report_document_styles()

        self.assertIn(".report-document-list-item {", styles)
        self.assertIn("orphans: 2", styles)
        self.assertIn("widows: 2", styles)
        self.assertIn(".report-document-block--continued .report-document-list", styles)

    def test_build_context_includes_document_script(self):
        """Garante script de paginação embutido no HTML do preview."""
        context = build_report_document_context(self.report, self._request())

        self.assertIn("paginateDocument", context["document_script"])
        self.assertIn("report-document-page-sheet", context["document_script"])
        self.assertIn("splitParagraphBlock", context["document_script"])
        self.assertIn("splitListBlock", context["document_script"])
        self.assertIn("splitElementAtPlainTextOffset", context["document_script"])

    def test_load_document_script_includes_inline_text_helpers(self):
        """Garante utilitários de quebra de linha disponíveis na paginação."""
        script = load_report_document_script()

        self.assertIn("splitHtmlIntoLineFragments", script)
        self.assertIn("splitParagraphBlock", script)
        self.assertIn("splitListBlock", script)
        self.assertIn("splitElementAtPlainTextOffset", script)

    def test_report_document_template_renders_standalone_html(self):
        """Garante HTML autônomo de leitura com CSS inline e blocos do laudo."""
        self._create_node(
            ReportBlockType.HEADING,
            {"text": "Introdução"},
            position=Decimal("1"),
        )

        context = build_report_document_context(self.report, self._request())
        html = render_to_string("reports/document/report_document.html", context)

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn('<html lang="pt-BR" class="report-document-preview-root">', html)
        self.assertIn("<style>", html)
        self.assertIn(".report-document-page-sheet {", html)
        self.assertIn('id="report-document-pages"', html)
        self.assertIn("report-document-pagination-source", html)
        self.assertIn("<script>", html)
        self.assertIn("paginateDocument", html)
        self.assertIn('class="report-document-block', html)
        self.assertIn("Introdução", html)
        self.assertNotIn("contenteditable", html)

    def test_page_layout_header_has_absolute_logo_url(self):
        """Garante URL absoluta de logo do cabeçalho no contexto de leitura."""
        layout = apply_header_template({}, HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT)
        layout = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload={
                "file": "reports/1/logo.png",
                "image_id": "logo-1",
                "width": 400,
                "height": 200,
                "alt": "Brasão",
            },
        )
        self.report.page_layout = layout
        self.report.save(update_fields=["page_layout"])

        context = build_report_document_context(self.report, self._request())
        logo_cell = context["page_layout"]["header"]["cells"][0]

        self.assertTrue(logo_cell["url"].startswith("http://testserver/"))
        self.assertIn("reports/1/logo.png", logo_cell["url"])
