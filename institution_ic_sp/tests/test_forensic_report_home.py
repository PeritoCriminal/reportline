# reportline/institution_ic_sp/tests/test_forensic_report_home.py
"""
Testes do card Novo relatório na página inicial.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP

User = get_user_model()


class ForensicReportHomeCardTests(TestCase):
    """Testes de opções de novo relatório na home."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários com e sem perfil pericial."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.examiner_user = User.objects.create_user(
            username="perito_home",
            password="senha-segura",
            first_name="Perito",
            last_name="Home",
        )
        cls.regular_user = User.objects.create_user(
            username="usuario_home",
            password="senha-segura",
        )
        ForensicExaminerSP.objects.create(
            user=cls.examiner_user,
            forensic_team=cls.team,
        )

    def test_examiner_sees_institutional_and_common_options(self):
        """Garante opções institucional e comum para ForensicExaminerSP."""
        self.client.login(username="perito_home", password="senha-segura")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Novo laudo pericial")
        self.assertContains(response, "Institucional")
        self.assertContains(response, "SPTC")
        self.assertContains(response, "Relatório Comum")
        self.assertContains(response, "Perito Home")
        self.assertContains(response, reverse("institution_ic_sp:forensic_report:intake"))
        self.assertContains(response, reverse("reports:new"))

    def test_regular_user_sees_only_common_option(self):
        """Garante apenas relatório comum para usuário sem perfil pericial."""
        self.client.login(username="usuario_home", password="senha-segura")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Institucional")
        self.assertNotContains(response, "Novo laudo pericial")
        self.assertContains(response, "Relatório Comum")
        self.assertContains(response, "usuario_home")
        self.assertContains(response, reverse("reports:new"))
