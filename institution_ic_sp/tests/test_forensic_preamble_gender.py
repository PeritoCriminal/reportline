"""
Testes de concordância de gênero no preâmbulo do laudo pericial.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.services.preamble import (
    build_preamble_paragraph,
    infer_requesting_authority_gender,
    requisition_authority_clause,
)
from institution_ic_sp.models import ForensicTeam, Institution
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class PreambleGenderInferenceTests(TestCase):
    """Testes de inferência Dr./Dra. na autoridade requisitante."""

    def test_dra_prefix_is_female(self):
        """Garante inferência feminina para prefixo Dra."""
        self.assertEqual(
            infer_requesting_authority_gender("Dra. Maria Silva"),
            GenderCalling.FEMALE,
        )

    def test_dr_prefix_is_male(self):
        """Garante inferência masculina para prefixo Dr."""
        self.assertEqual(
            infer_requesting_authority_gender("Dr. João Silva"),
            GenderCalling.MALE,
        )

    def test_no_prefix_is_neutral(self):
        """Garante texto neutro quando honorífico estiver ausente."""
        self.assertIsNone(infer_requesting_authority_gender("Fulano de Tal"))


class PreambleComposeTests(TestCase):
    """Testes de composição do preâmbulo com concordância gramatical."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito, instituição e metadados de caso."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.author = User.objects.create_user(
            username="perito_preamble",
            password="senha-segura",
        )
        cls.institution = Institution.objects.get(acronym="IC-SP")
        cls.institution.director_display = "Dr. Diretor Institucional"
        cls.institution.save(update_fields=["director_display", "updated_at"])

    def _build(self, *, authority: str, calling_gender: str) -> str:
        examiner = ForensicExaminerSP.objects.create(
            user=self.author,
            forensic_team=self.team,
            display_name="Dra. Perita Teste",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=calling_gender,
            director_display="Dr. Diretor Perfil",
        )
        metadata = CaseMetadata(
            report_number="1",
            report_year=2026,
            designation_date=date(2026, 4, 1),
            requesting_authority=authority,
            examiner="Dra. Perita Teste",
        )
        return build_preamble_paragraph(
            metadata,
            examiner=examiner,
            institution=self.institution,
        )

    def test_preamble_uses_female_delegate_clause_for_dra_authority(self):
        """Garante cláusula feminina quando autoridade inicia com Dra."""
        text = self._build(authority="Dra. Delegada Example", calling_gender=GenderCalling.FEMALE)
        self.assertIn("pela Exma. Sra. Delegada de Polícia Dra. Delegada Example", text)
        self.assertIn("foi designada a Perita Criminal", text)

    def test_preamble_uses_male_delegate_clause_for_dr_authority(self):
        """Garante cláusula masculina quando autoridade inicia com Dr."""
        user = User.objects.create_user(username="perito2", password="senha-segura")
        examiner = ForensicExaminerSP.objects.create(
            user=user,
            forensic_team=self.team,
            display_name="Dr. Perito Teste",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )
        metadata = CaseMetadata(
            report_number="2",
            report_year=2026,
            designation_date=date(2026, 4, 2),
            requesting_authority="Dr. Delegado Example",
            examiner="Dr. Perito Teste",
        )
        text = build_preamble_paragraph(
            metadata,
            examiner=examiner,
            institution=self.institution,
        )
        self.assertIn("pelo Exmo. Sr. Delegado de Polícia Dr. Delegado Example", text)
        self.assertIn("foi designado o Perito Criminal", text)

    def test_neutral_clause_without_honorific_prefix(self):
        """Garante cláusula neutra sem impor Dr./Dra. quando prefixo ausente."""
        clause = requisition_authority_clause(requesting_authority_gender=None)
        self.assertEqual(clause, "pelo(a) Exmo(a). Sr(a). Delegado(a) de Polícia")
