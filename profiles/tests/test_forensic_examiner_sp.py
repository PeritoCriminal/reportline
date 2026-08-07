# reportline/profiles/tests/test_forensic_examiner_sp.py
"""
Testes do model ForensicExaminerSP e suas regras de vínculo.

Valida relação 1:1 com CustomUser, lotação N:1 em ForensicTeam e
proteção contra exclusão de equipe com peritos lotados.
"""

import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase

from institution_ic_sp.models import ForensicNucleus, ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class ForensicExaminerSPModelTests(TestCase):
    """Testes do perfil profissional do perito criminal (SP)."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e equipe pericial para os cenários de teste."""
        cls.team_centro = ForensicTeam.objects.get(code="EPC-SPC")
        cls.team_norte = ForensicTeam.objects.get(code="EPC-SPN")
        cls.nucleus_americana = ForensicNucleus.objects.get(code="NPC-AME")
        cls.user_one = User.objects.create_user(
            username="perito1",
            password="senha-segura",
        )
        cls.user_two = User.objects.create_user(
            username="perito2",
            password="senha-segura",
        )

    def test_primary_key_is_uuid(self):
        """Garante que a chave primária do perito seja UUID, não inteiro sequencial."""
        examiner = ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Um",
            forensic_team=self.team_centro,
        )
        self.assertIsInstance(examiner.pk, uuid.UUID)

    def test_user_has_at_most_one_examiner_profile(self):
        """Impede mais de um perfil ForensicExaminerSP para o mesmo CustomUser."""
        ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Um",
            forensic_team=self.team_centro,
        )
        duplicate = ForensicExaminerSP(
            user=self.user_one,
            display_name="Outro nome",
            forensic_team=self.team_norte,
        )

        with self.assertRaises(Exception):
            duplicate.save()

    def test_team_supports_multiple_examiners(self):
        """Garante relação N:1 — vários peritos podem compartilhar a mesma equipe."""
        examiner_one = ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Um",
            forensic_team=self.team_centro,
        )
        examiner_two = ForensicExaminerSP.objects.create(
            user=self.user_two,
            display_name="Dra. Perita Dois",
            forensic_team=self.team_centro,
        )

        self.assertEqual(examiner_one.forensic_team, examiner_two.forensic_team)
        self.assertEqual(self.team_centro.examiners.count(), 2)

    def test_cannot_delete_team_with_assigned_examiners(self):
        """Bloqueia exclusão de equipe pericial quando há peritos lotados nela."""
        ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Um",
            forensic_team=self.team_centro,
        )

        with self.assertRaises(ProtectedError):
            self.team_centro.delete()

    def test_verbose_name_is_perito_criminal_sp(self):
        """Garante rótulos administrativos em português conforme definição do model."""
        meta = ForensicExaminerSP._meta

        self.assertEqual(meta.verbose_name, "Perito criminal (SP)")
        self.assertEqual(meta.verbose_name_plural, "Peritos criminais (SP)")

    def test_has_full_institution_access_only_for_perito_criminal(self):
        """Garante que apenas peritos criminais tenham acesso amplo às páginas institucionais."""
        perito = ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Um",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            forensic_team=self.team_centro,
        )
        fotografo = ForensicExaminerSP.objects.create(
            user=self.user_two,
            display_name="Fotógrafo Dois",
            job_title=ForensicJobTitle.FOTOGRAFO_TECNICO,
            forensic_team=self.team_centro,
        )

        self.assertTrue(perito.has_full_institution_access)
        self.assertFalse(fotografo.has_full_institution_access)

    def test_is_profile_complete_requires_display_name_job_title_and_gender(self):
        """Garante perfil completo apenas com nome, cargo e tratamento gramatical."""
        incomplete = ForensicExaminerSP.objects.create(
            user=self.user_one,
            forensic_team=self.team_centro,
        )
        complete = ForensicExaminerSP(
            user=self.user_two,
            display_name="Dra. Perita Dois",
            job_title=ForensicJobTitle.DESENHISTA_TECNICO,
            calling_gender=GenderCalling.FEMALE,
            forensic_team=self.team_norte,
        )

        self.assertFalse(incomplete.is_profile_complete)
        complete.save()
        self.assertTrue(complete.is_profile_complete)

    def test_nucleus_direct_assignment_without_team(self):
        """Garante lotação direta no núcleo sem equipe pericial vinculada."""
        examiner = ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Americana",
            forensic_nucleus=self.nucleus_americana,
        )

        self.assertTrue(examiner.is_nucleus_direct_assignment)
        self.assertIsNone(examiner.forensic_team)
        self.assertEqual(examiner.assigned_nucleus, self.nucleus_americana)

    def test_assigned_nucleus_is_inferred_from_team(self):
        """Garante que o núcleo seja inferido pela equipe quando houver lotação em EPC."""
        examiner = ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Centro",
            forensic_team=self.team_centro,
        )

        self.assertFalse(examiner.is_nucleus_direct_assignment)
        self.assertEqual(examiner.assigned_nucleus, self.team_centro.nucleus)

    def test_cannot_assign_both_team_and_nucleus(self):
        """Impede lotação simultânea em equipe e núcleo pericial."""
        examiner = ForensicExaminerSP(
            user=self.user_one,
            display_name="Dr. Perito Um",
            forensic_team=self.team_centro,
            forensic_nucleus=self.nucleus_americana,
        )

        with self.assertRaises(ValidationError):
            examiner.save()

    def test_must_assign_team_or_nucleus(self):
        """Exige lotação em equipe ou núcleo pericial."""
        examiner = ForensicExaminerSP(
            user=self.user_one,
            display_name="Dr. Perito Um",
        )

        with self.assertRaises(ValidationError):
            examiner.save()

    def test_cannot_delete_nucleus_with_direct_examiners(self):
        """Bloqueia exclusão de núcleo com servidores lotados diretamente nele."""
        ForensicExaminerSP.objects.create(
            user=self.user_one,
            display_name="Dr. Perito Americana",
            forensic_nucleus=self.nucleus_americana,
        )

        with self.assertRaises(ProtectedError):
            self.nucleus_americana.delete()
