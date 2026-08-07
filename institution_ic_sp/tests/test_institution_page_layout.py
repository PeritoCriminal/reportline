# reportline/institution_ic_sp/tests/test_institution_page_layout.py
"""
Testes do cabeçalho institucional de laudos periciais do IC-SP.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.forensic_report.services.institution_page_layout import (
    INSTITUTION_FOOTER_DISCLAIMER_LINE_1,
    INSTITUTION_FOOTER_DISCLAIMER_LINE_2,
    INSTITUTION_HEADER_IC,
    INSTITUTION_HEADER_SECURITY_SECRETARIAT,
    INSTITUTION_HEADER_SPTC,
    build_institution_page_layout,
)
from institution_ic_sp.models import ForensicNucleus, ForensicTeam, Institution
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.services.report_creation import create_report
from reports.services.report_page_layout import (
    HEADER_EXTRA_ROW_TYPE_RULE,
    HEADER_LOGO_INITIAL_WIDTH_PX,
    initial_header_logo_display_size_by_width,
)

User = get_user_model()


class InstitutionPageLayoutTests(TestCase):
    """Testes da montagem do cabeçalho institucional do IC-SP."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito, equipe e laudo para montagem do layout."""
        cls.institution = Institution.objects.get(acronym="IC-SP")
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.team.address = "Av. Ângelo Pascote, 90. CEP 13.478-800 - Americana - SP"
        cls.team.phone = "(19) 3406-5155"
        cls.team.institutional_email = "americana.ic@policiacientifica.sp.gov.br"
        cls.team.save(
            update_fields=[
                "address",
                "phone",
                "institutional_email",
                "updated_at",
            ]
        )

        cls.author = User.objects.create_user(
            username="perito_header",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.author,
            forensic_team=cls.team,
            display_name="Dr. Header",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_header_text_uses_institutional_lines_and_team_contact(self):
        """Garante texto fixo institucional e dados de contato da equipe pericial."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        layout = build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=self.examiner,
            workflow="generic",
            main_title_text="LAUDO PERICIAL Nº 1/2026",
        )

        header_text = layout["header"]["cells"][1]["text"]
        self.assertIn(INSTITUTION_HEADER_SECURITY_SECRETARIAT, header_text)
        self.assertIn(INSTITUTION_HEADER_SPTC, header_text)
        self.assertIn(INSTITUTION_HEADER_IC, header_text)
        self.assertIn("Perito Criminal Dr. Octávio Eduardo de Brito Alvarenga", header_text)
        self.assertIn(self.team.nucleus.name, header_text)
        self.assertIn(self.team.address, header_text)
        self.assertIn("(19) 3406-5155", header_text)
        self.assertIn("americana.ic@policiacientifica.sp.gov.br", header_text)

    def test_header_text_applies_institutional_line_styles(self):
        """Garante negrito e tamanhos de fonte por linha do cabeçalho institucional."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        layout = build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=self.examiner,
            workflow="generic",
        )

        header_text = layout["header"]["cells"][1]["text"]
        self.assertIn("<strong>", header_text)
        self.assertIn("report-inline-font-md", header_text)
        self.assertIn("report-inline-font-sm", header_text)
        self.assertIn(
            "<strong><span class=\"report-inline-font-md\">"
            f"{INSTITUTION_HEADER_SECURITY_SECRETARIAT}</span></strong>",
            header_text,
        )
        self.assertIn(
            "<strong><span class=\"report-inline-font-sm\">"
            f"{INSTITUTION_HEADER_SPTC}</span></strong>",
            header_text,
        )
        self.assertIn("|", header_text)

    def test_header_text_uses_nucleus_contact_when_examiner_is_nucleus_assigned(self):
        """Garante dados de contato do núcleo quando perito está lotado diretamente nele."""
        nucleus = ForensicNucleus.objects.get(code="NPC-AME")
        nucleus.address = "Av. Ângelo Pascote, 90. CEP 13.478-800 - Americana - SP"
        nucleus.phone = "(19) 3406-5155"
        nucleus.institutional_email = "americana.ic@policiacientifica.sp.gov.br"
        nucleus.save(
            update_fields=[
                "address",
                "phone",
                "institutional_email",
                "updated_at",
            ]
        )

        nucleus_author = User.objects.create_user(
            username="perito_nucleo",
            password="senha-segura",
        )
        nucleus_examiner = ForensicExaminerSP.objects.create(
            user=nucleus_author,
            forensic_nucleus=nucleus,
            display_name="Dr. Nucleo",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

        report = create_report(author=nucleus_author, title="Laudo pericial 2/2026")
        layout = build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=nucleus_examiner,
            workflow="generic",
        )

        header_text = layout["header"]["cells"][1]["text"]
        self.assertIn(nucleus.name, header_text)
        self.assertIn(nucleus.address, header_text)
        self.assertIn("(19) 3406-5155", header_text)
        self.assertIn("americana.ic@policiacientifica.sp.gov.br", header_text)

    def test_header_extra_rows_include_rule_and_report_number(self):
        """Garante linha horizontal e número do laudo alinhado à direita."""
        report = create_report(author=self.author, title="Laudo pericial 42/2026")
        layout = build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=self.examiner,
            workflow="generic",
            main_title_text="Laudo pericial nº 42/2026",
        )

        extra_rows = layout["header"]["extra_rows"]
        self.assertEqual(len(extra_rows), 2)
        self.assertEqual(extra_rows[0]["type"], HEADER_EXTRA_ROW_TYPE_RULE)
        self.assertEqual(extra_rows[1]["align"], "right")
        self.assertIn("Laudo pericial nº 42/2026", extra_rows[1]["text"])
        self.assertIn("report-inline-font-sm", extra_rows[1]["text"])

    def test_footer_text_uses_institutional_disclaimer_with_styles(self):
        """Garante aviso institucional do rodapé com 10 pt, itálico e numeração ativa."""
        report = create_report(author=self.author, title="Laudo pericial 1/2026")
        layout = build_institution_page_layout(
            report,
            institution=self.institution,
            examiner=self.examiner,
            workflow="generic",
        )

        footer = layout["footer"]
        self.assertTrue(footer["enabled"])
        footer_cell = footer["cells"][0]
        footer_text = footer_cell["text"]

        self.assertEqual(footer_cell["align"], "center")
        self.assertEqual(footer_cell["indent_level"], 0)
        self.assertFalse(footer_cell["first_line_indent"])
        self.assertTrue(footer_cell["show_page_number"])
        self.assertIn(INSTITUTION_FOOTER_DISCLAIMER_LINE_1, footer_text)
        self.assertIn(INSTITUTION_FOOTER_DISCLAIMER_LINE_2, footer_text)
        self.assertIn("Superintendência da Polícia Técnico-Científica", footer_text)
        self.assertIn("<em>", footer_text)
        self.assertIn("report-inline-font-xs", footer_text)
        self.assertIn("<br>", footer_text)

    def test_initial_header_logo_display_size_by_width_preserves_aspect_ratio(self):
        """Garante largura inicial fixa de 1,5 cm com altura proporcional."""
        width, height = initial_header_logo_display_size_by_width(400, 200)
        self.assertEqual(width, HEADER_LOGO_INITIAL_WIDTH_PX)
        self.assertEqual(height, HEADER_LOGO_INITIAL_WIDTH_PX // 2)
