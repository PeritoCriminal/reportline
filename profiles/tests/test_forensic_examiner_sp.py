"""
Testes do model ForensicExaminerSP e suas regras de vínculo.

Valida relação 1:1 com CustomUser, lotação N:1 em ForensicTeam e
proteção contra exclusão de equipe com peritos lotados.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP

User = get_user_model()


class ForensicExaminerSPModelTests(TestCase):
    """Testes do perfil profissional do perito criminal (SP)."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e equipe pericial para os cenários de teste."""
        cls.team_centro = ForensicTeam.objects.get(code="EPC-SPC")
        cls.team_norte = ForensicTeam.objects.get(code="EPC-SPN")
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
