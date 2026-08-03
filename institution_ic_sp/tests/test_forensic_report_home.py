"""
Testes do card de laudo pericial na página inicial.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP

User = get_user_model()


class ForensicReportHomeCardTests(TestCase):
    """Testes de exibição do card de laudo pericial na home."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários com e sem perfil pericial."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.examiner_user = User.objects.create_user(
            username="perito_home",
            password="senha-segura",
        )
        cls.regular_user = User.objects.create_user(
            username="usuario_home",
            password="senha-segura",
        )
        ForensicExaminerSP.objects.create(
            user=cls.examiner_user,
            forensic_team=cls.team,
        )

    def test_examiner_sees_forensic_report_card(self):
        """Garante card de laudo pericial visível para ForensicExaminerSP."""
        self.client.login(username="perito_home", password="senha-segura")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo laudo pericial")
        self.assertContains(response, reverse("institution_ic_sp:forensic_report:intake"))

    def test_regular_user_does_not_see_forensic_report_card(self):
        """Garante ausência do card para usuário sem perfil pericial."""
        self.client.login(username="usuario_home", password="senha-segura")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Novo laudo pericial")
