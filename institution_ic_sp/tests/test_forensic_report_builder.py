"""
Testes do builder de laudo pericial genérico.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.workflows.generic.services.report_draft_builder import (
    CLOSING_PHRASE,
    build_generic_forensic_report_draft,
)
from institution_ic_sp.models import ForensicTeam, Institution
from profiles.models import ForensicExaminerSP, ForensicJobTitle
from reports.models import ReportBlockType
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
        )
        cls.metadata = CaseMetadata(
            report_number="42",
            report_year=2026,
            service_protocol="2026/001234",
            requester="Delegacia Central",
            case_type="Furto qualificado",
            bulletin_number="BO-987654",
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
        self.assertEqual(len(blocks), 11)

        main_title = blocks[0]
        self.assertEqual(main_title[0], ReportBlockType.HEADING)
        self.assertEqual(main_title[2], 0)
        self.assertEqual(main_title[1]["text"], "LAUDO PERICIAL Nº 42/2026")

        headings = [
            content["text"]
            for block_type, content, _level in blocks
            if block_type == ReportBlockType.HEADING and content["text"] != "LAUDO PERICIAL Nº 42/2026"
        ]
        self.assertEqual(
            headings,
            ["Objetivo do Exame", "Dados da Requisição", "Dados do Atendimento"],
        )

        closing_blocks = [content["text"] for block_type, content, _ in blocks if block_type == ReportBlockType.PARAGRAPH]
        self.assertIn(CLOSING_PHRASE, closing_blocks)
        self.assertIn("Dr. Builder", closing_blocks[-1])

    def test_builder_enables_institution_page_layout(self):
        """Garante cabeçalho institucional ativo no laudo gerado."""
        report = build_generic_forensic_report_draft(
            author=self.author,
            examiner=self.examiner,
            metadata=self.metadata,
        )

        institution = Institution.objects.get(acronym="IC-SP")
        header = report.page_layout["header"]

        self.assertTrue(header["enabled"])
        self.assertIn(institution.name, header["cells"][1]["text"])
