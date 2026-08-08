# reportline/institution_ic_sp/tests/test_case_metadata_casing.py
"""
Testes das regras de caixa alta/baixa nos metadados do intake.
"""

from django.test import SimpleTestCase

from institution_ic_sp.forensic_report.common.forms.case_intake_form import CaseIntakeForm
from institution_ic_sp.forensic_report.common.services.case_metadata import (
    CaseMetadata,
    format_portuguese_proper_name,
    format_report_number_display,
    normalize_case_metadata,
    normalize_text_field,
)


class CaseMetadataCasingTests(SimpleTestCase):
    """Testes de normalização de caixa nos campos do intake."""

    def test_identifier_fields_are_uppercased(self):
        """Garante caixa alta em identificadores administrativos."""
        metadata = normalize_case_metadata(
            CaseMetadata(
                report_number="42-a",
                attendance_protocol="2026/0007",
                occurrence_report="bo-123",
                police_inquiry="ip 456",
            )
        )

        self.assertEqual(metadata.report_number, "42-A")
        self.assertEqual(metadata.attendance_protocol, "2026/0007")
        self.assertEqual(metadata.occurrence_report, "BO-123")
        self.assertEqual(metadata.police_inquiry, "IP 456")

    def test_name_fields_receive_portuguese_proper_casing(self):
        """Garante capitalização normativa em campos de nomes próprios."""
        metadata = normalize_case_metadata(
            CaseMetadata(
                requesting_authority="DR. JOÃO DA SILVA",
                police_district="1º DISTRITO INTEGRADO DE POLÍCIA",
                examiner="dra. maria das dores",
                photography="carlos fotógrafo",
                scanning_3d="técnico 3d",
                sketch="desenhista croqui",
                exam_objective="Examinar vestígios.",
            )
        )

        self.assertEqual(metadata.requesting_authority, "Dr. João da Silva")
        self.assertEqual(metadata.police_district, "1º Distrito Integrado de Polícia")
        self.assertEqual(metadata.examiner, "Dra. Maria das Dores")
        self.assertEqual(metadata.photography, "Carlos Fotógrafo")
        self.assertEqual(metadata.scanning_3d, "Técnico 3D")
        self.assertEqual(metadata.sketch, "Desenhista Croqui")
        self.assertEqual(metadata.exam_objective, "Examinar vestígios.")

    def test_format_portuguese_proper_name_keeps_particles_lowercase(self):
        """Garante preposições/artigos em minúsculas no meio do nome."""
        self.assertEqual(
            format_portuguese_proper_name("jose da silva"),
            "Jose da Silva",
        )
        self.assertEqual(
            format_portuguese_proper_name("Maria Das Dores"),
            "Maria das Dores",
        )
        self.assertEqual(
            format_portuguese_proper_name("Ana-Paula de Souza e Costa"),
            "Ana-Paula de Souza e Costa",
        )

    def test_format_portuguese_proper_name_preserves_mixed_acronyms(self):
        """Garante preservação de siglas curtas em entradas mistas."""
        self.assertEqual(format_portuguese_proper_name("1º DP"), "1º DP")
        self.assertEqual(format_portuguese_proper_name("DEIC"), "DEIC")

    def test_normalize_text_field_applies_field_rules(self):
        """Garante que a função pontual respeita o nome do campo."""
        self.assertEqual(normalize_text_field("occurrence_report", "bo-1"), "BO-1")
        self.assertEqual(
            normalize_text_field("requesting_authority", "jose da silva"),
            "Jose da Silva",
        )
        self.assertEqual(
            normalize_text_field("exam_objective", "examinar vestígios."),
            "examinar vestígios.",
        )

    def test_intake_form_applies_uppercase_widget_only_to_identifiers(self):
        """Garante classe visual de caixa alta só nos campos identificadores."""
        form = CaseIntakeForm()

        for name in ("report_number", "attendance_protocol", "occurrence_report", "police_inquiry"):
            css_class = form.fields[name].widget.attrs.get("class", "")
            self.assertIn("text-uppercase", css_class)

        for name in (
            "requesting_authority",
            "police_district",
            "examiner",
            "photography",
            "scanning_3d",
            "sketch",
        ):
            css_class = form.fields[name].widget.attrs.get("class", "")
            self.assertNotIn("text-uppercase", css_class)

    def test_intake_form_normalizes_identifiers_on_submit(self):
        """Garante persistência em caixa alta para identificadores no submit."""
        form = CaseIntakeForm(
            data={
                "report_number": "7",
                "report_year": "2026",
                "requesting_authority": "Dr. Delegado",
                "occurrence_report": "bo-1",
                "attendance_protocol": "2026/0007",
                "police_inquiry": "ip 9",
            }
        )

        self.assertTrue(form.is_valid())
        metadata = form.to_case_metadata()

        self.assertEqual(metadata.occurrence_report, "BO-1")
        self.assertEqual(metadata.attendance_protocol, "2026/0007")
        self.assertEqual(metadata.police_inquiry, "IP 9")
        self.assertEqual(metadata.requesting_authority, "Dr. Delegado")

    def test_format_report_number_display_uses_thousand_separator(self):
        """Garante separador de milhar na exibição institucional do número do laudo."""
        self.assertEqual(format_report_number_display("123212"), "123.212")
        self.assertEqual(format_report_number_display("42"), "42")
        self.assertEqual(format_report_number_display("42-A"), "42-A")

        metadata = CaseMetadata(report_number="123212", report_year=2026)
        self.assertEqual(metadata.header_report_number_text, "Laudo pericial nº 123.212/2026")
        self.assertEqual(metadata.main_title_text, "LAUDO PERICIAL Nº 123.212/2026")
