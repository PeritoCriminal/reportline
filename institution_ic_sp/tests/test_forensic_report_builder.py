# reportline/institution_ic_sp/tests/test_forensic_report_builder.py
"""
Testes do builder de laudo pericial genérico.
"""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.services.forensic_report_body_builder import (
    CLOSING_DIGITAL_ARCHIVE_NOTICE,
    CLOSING_PHRASE,
)
from institution_ic_sp.forensic_report.workflows.initial_data.services.report_draft_builder import (
    build_generic_forensic_report_draft,
)
from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import ReportBlockType
from reports.models.report_block import ReportBlockLineSpacing
from reports.services.report_kind import is_forensic_report

User = get_user_model()


class GenericForensicReportBuilderTests(TestCase):
    """Testes da geração de rascunho de laudo pericial genérico."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito e metadados de caso."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.author = User.objects.create_user(
            username="perito_builder",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.author,
            forensic_team=cls.team,
            display_name="Dr. Builder",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
            director_display="Dr. Diretor",
        )
        cls.metadata = CaseMetadata(
            report_number="42",
            report_year=2026,
            designation_date=date(2026, 3, 10),
            requesting_authority="Dr. Delegado Central",
            police_district="DEIC",
            occurrence_report="BO-987654",
            attendance_protocol="2026/001234",
            examiner="Dr. Builder",
            examination_at=timezone.make_aware(datetime(2026, 3, 11, 9, 15)),
            exam_objective="Determinar vestígios papiloscópicos.",
        )

    def test_builder_creates_structured_report(self):
        """Garante árvore de blocos com seções padronizadas do laudo genérico."""
        report = build_generic_forensic_report_draft(
            author=self.author,
            examiner=self.examiner,
            metadata=self.metadata,
        )

        blocks = list(
            report.nodes.select_related("block").order_by("position").values_list(
                "block__block_type",
                "block__content",
                "block__title_level",
            )
        )

        self.assertEqual(report.title, "Laudo pericial 42/2026")
        self.assertTrue(is_forensic_report(report))

        main_title = blocks[0]
        self.assertEqual(main_title[1]["text"], "LAUDO PERICIAL Nº 42/2026")

        preamble_block = report.nodes.select_related("block").order_by("position")[1].block
        self.assertEqual(preamble_block.block_type, ReportBlockType.PARAGRAPH)
        self.assertEqual(preamble_block.indent_level, 5)
        self.assertEqual(preamble_block.line_spacing, ReportBlockLineSpacing.COMPACT)
        self.assertFalse(preamble_block.first_line_indent)
        self.assertIn("report-inline-font-xs", preamble_block.content["text"])
        self.assertIn("report-inline-font-serif", preamble_block.content["text"])

        preamble_text = blocks[1][1]["text"]
        self.assertIn("Aos 10 de março de 2026", preamble_text)
        self.assertIn("pelo Exmo. Sr. Delegado de Polícia Dr. Delegado Central", preamble_text)

        headings = [
            (content["text"], level)
            for block_type, content, level in blocks
            if block_type == ReportBlockType.HEADING
            and content["text"] != "LAUDO PERICIAL Nº 42/2026"
        ]
        self.assertEqual(
            [text for text, _level in headings],
            ["Objetivo do Exame", "Dados da Requisição", "Dados do Atendimento"],
        )
        self.assertTrue(all(level == 0 for _text, level in headings))

        list_blocks = [
            content["items"]
            for block_type, content, _ in blocks
            if block_type == ReportBlockType.UNORDERED_LIST
        ]
        all_list_items = [item for items in list_blocks for item in items]
        self.assertIn("Boletim de ocorrência: BO-987654", all_list_items)
        self.assertTrue(any("Número do protocolo" in item for item in all_list_items))

        closing_blocks = [
            content["text"] for block_type, content, _ in blocks if block_type == ReportBlockType.PARAGRAPH
        ]
        self.assertTrue(any(CLOSING_PHRASE in text for text in closing_blocks))
        self.assertIn(CLOSING_DIGITAL_ARCHIVE_NOTICE, closing_blocks)

    def test_builder_closing_section_uses_institutional_phrase_and_signature(self):
        """Garante fechamento institucional em itálico, aviso GDL e assinatura alinhada."""
        report = build_generic_forensic_report_draft(
            author=self.author,
            examiner=self.examiner,
            metadata=self.metadata,
        )

        closing_nodes = list(
            report.nodes.select_related("block")
            .order_by("-position")[:4]
        )
        closing_nodes.reverse()

        _empty_block, phrase_block, archive_block, signature_block = [
            node.block for node in closing_nodes
        ]

        self.assertEqual(phrase_block.content["text"], f"<em>{CLOSING_PHRASE}</em>")
        self.assertEqual(archive_block.content["text"], CLOSING_DIGITAL_ARCHIVE_NOTICE)
        self.assertEqual(
            signature_block.content["text"],
            "Dr. Builder<br>Perito Criminal",
        )
        self.assertEqual(signature_block.text_align, "right")

    def test_builder_omits_empty_list_sections(self):
        """Garante ausência de lista quando seção não possui itens preenchidos."""
        sparse_metadata = CaseMetadata(
            report_number="1",
            report_year=2026,
            designation_date=date(2026, 1, 1),
        )
        report = build_generic_forensic_report_draft(
            author=self.author,
            examiner=self.examiner,
            metadata=sparse_metadata,
        )
        list_count = report.nodes.filter(
            block__block_type=ReportBlockType.UNORDERED_LIST,
        ).count()
        self.assertEqual(list_count, 0)

    def test_header_report_number_text_uses_normal_case(self):
        """Garante texto do número do laudo no cabeçalho em caixa normal."""
        self.assertEqual(
            self.metadata.header_report_number_text,
            "Laudo pericial nº 42/2026",
        )
        self.assertEqual(
            self.metadata.main_title_text,
            "LAUDO PERICIAL Nº 42/2026",
        )

    def test_builder_enables_institution_page_layout(self):
        """Garante cabeçalho institucional ativo no laudo gerado."""
        report = build_generic_forensic_report_draft(
            author=self.author,
            examiner=self.examiner,
            metadata=self.metadata,
        )

        header = report.page_layout["header"]

        self.assertTrue(header["enabled"])
        self.assertIn("SECRETARIA DA SEGURANÇA PÚBLICA", header["cells"][1]["text"])
        self.assertEqual(len(header["extra_rows"]), 2)
        self.assertIn("Laudo pericial nº 42/2026", header["extra_rows"][1]["text"])
        self.assertIn("report-inline-font-sm", header["extra_rows"][1]["text"])
        self.assertEqual(header["extra_rows"][1]["align"], "right")
