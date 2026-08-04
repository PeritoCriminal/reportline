"""
Testes da view de edição do perfil profissional ForensicExaminerSP.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.models import ForensicNucleus, ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class ForensicExaminerSPProfileViewTests(TestCase):
    """Testes do formulário de perfil profissional do servidor pericial (SP)."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e equipe pericial para os cenários de teste."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.linked_user = User.objects.create_user(
            username="servidor1",
            password="senha-segura",
        )
        cls.unlinked_user = User.objects.create_user(
            username="staff1",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.linked_user,
            forensic_team=cls.team,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante que visitantes não autenticados sejam enviados ao login."""
        response = self.client.get(reverse("profiles:forensic_examiner_sp"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('profiles:forensic_examiner_sp')}",
        )

    def test_user_without_profile_receives_404(self):
        """Garante 404 para usuário autenticado sem vínculo ForensicExaminerSP."""
        self.client.login(username="staff1", password="senha-segura")
        response = self.client.get(reverse("profiles:forensic_examiner_sp"))
        self.assertEqual(response.status_code, 404)

    def test_linked_user_sees_profile_form(self):
        """Garante que usuário vinculado veja o formulário com lotação e campos editáveis."""
        self.client.login(username="servidor1", password="senha-segura")
        response = self.client.get(reverse("profiles:forensic_examiner_sp"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perfil profissional")
        self.assertContains(response, self.team.name)
        self.assertContains(response, "Nome de exibição no laudo")
        self.assertContains(response, "Perito Criminal")

    def test_linked_user_can_save_display_name_and_job_title(self):
        """Garante persistência de nome de exibição e cargo pelo próprio servidor."""
        self.client.login(username="servidor1", password="senha-segura")
        response = self.client.post(
            reverse("profiles:forensic_examiner_sp"),
            {
                "display_name": "Dr. Servidor Um",
                "job_title": ForensicJobTitle.PERITO_CRIMINAL,
                "calling_gender": GenderCalling.MALE,
                "director_display": "Dr. Diretor Institucional",
            },
        )

        self.assertRedirects(response, reverse("profiles:forensic_examiner_sp"))
        self.examiner.refresh_from_db()
        self.assertEqual(self.examiner.display_name, "Dr. Servidor Um")
        self.assertEqual(self.examiner.job_title, ForensicJobTitle.PERITO_CRIMINAL)
        self.assertEqual(self.examiner.calling_gender, GenderCalling.MALE)
        self.assertTrue(self.examiner.is_profile_complete)

    def test_missing_required_fields_show_inline_errors(self):
        """Garante erros inline quando nome ou cargo não são informados."""
        self.client.login(username="servidor1", password="senha-segura")
        response = self.client.post(
            reverse("profiles:forensic_examiner_sp"),
            {"display_name": "", "job_title": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")

    def test_nucleus_assignment_shows_nucleus_without_team(self):
        """Garante exibição de lotação direta no núcleo sem equipe pericial."""
        nucleus_user = User.objects.create_user(
            username="servidor_ame",
            password="senha-segura",
        )
        nucleus = ForensicNucleus.objects.get(code="NPC-AME")
        ForensicExaminerSP.objects.create(
            user=nucleus_user,
            forensic_nucleus=nucleus,
        )

        self.client.login(username="servidor_ame", password="senha-segura")
        response = self.client.get(reverse("profiles:forensic_examiner_sp"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, nucleus.name)
        self.assertContains(response, "Lotação direta no núcleo")
        self.assertNotContains(response, "Equipe")
