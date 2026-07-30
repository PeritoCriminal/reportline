"""
Testes do formulário administrativo ForensicExaminerSPAdminForm.

Valida lotação encadeada por núcleo e equipe opcional.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.models import ForensicNucleus, ForensicTeam
from profiles.forms.forensic_examiner_sp_admin_form import ForensicExaminerSPAdminForm
from profiles.models import ForensicExaminerSP

User = get_user_model()


class ForensicExaminerSPAdminFormTests(TestCase):
    """Testes da lotação encadeada no admin."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuário, núcleo e equipe para os cenários de teste."""
        cls.user = User.objects.create_user(
            username="servidor_admin",
            password="senha-segura",
        )
        cls.nucleus_americana = ForensicNucleus.objects.get(code="NPC-AME")
        cls.nucleus_capital = ForensicNucleus.objects.get(code="NPC-CAP")
        cls.team_limeira = ForensicTeam.objects.get(code="EPC-LIM")
        cls.team_centro = ForensicTeam.objects.get(code="EPC-SPC")

    def test_save_nucleus_only_assignment(self):
        """Garante persistência de lotação direta no núcleo sem equipe."""
        form = ForensicExaminerSPAdminForm(
            data={
                "user": str(self.user.pk),
                "display_name": "",
                "job_title": "",
                "lotacao_nucleus": str(self.nucleus_americana.pk),
                "forensic_team": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        examiner = form.save()

        self.assertEqual(examiner.forensic_nucleus, self.nucleus_americana)
        self.assertIsNone(examiner.forensic_team)

    def test_save_team_assignment_clears_nucleus_field(self):
        """Garante que lotação em equipe persista somente em forensic_team."""
        form = ForensicExaminerSPAdminForm(
            data={
                "user": str(self.user.pk),
                "display_name": "",
                "job_title": "",
                "lotacao_nucleus": str(self.nucleus_americana.pk),
                "forensic_team": str(self.team_limeira.pk),
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        examiner = form.save()

        self.assertEqual(examiner.forensic_team, self.team_limeira)
        self.assertIsNone(examiner.forensic_nucleus)

    def test_rejects_team_outside_selected_nucleus(self):
        """Impede seleção de equipe que não pertence ao núcleo escolhido."""
        form = ForensicExaminerSPAdminForm(
            data={
                "user": str(self.user.pk),
                "display_name": "",
                "job_title": "",
                "lotacao_nucleus": str(self.nucleus_americana.pk),
                "forensic_team": str(self.team_centro.pk),
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("forensic_team", form.errors)

    def test_edit_team_assignment_prefills_nucleus(self):
        """Garante que edição de lotação em equipe preencha o núcleo correspondente."""
        examiner = ForensicExaminerSP.objects.create(
            user=self.user,
            forensic_team=self.team_limeira,
        )
        form = ForensicExaminerSPAdminForm(instance=examiner)

        self.assertEqual(
            form.initial.get("lotacao_nucleus"),
            self.nucleus_americana.pk,
        )
        self.assertIn(self.team_limeira, form.fields["forensic_team"].queryset)

    def test_teams_queryset_is_empty_without_nucleus(self):
        """Garante que equipes fiquem indisponíveis até selecionar um núcleo."""
        form = ForensicExaminerSPAdminForm()

        self.assertEqual(form.fields["forensic_team"].queryset.count(), 0)

    def test_teams_by_nucleus_admin_endpoint(self):
        """Garante endpoint auxiliar do admin com equipes filhas do núcleo."""
        admin_user = User.objects.create_superuser(
            username="admin1",
            password="senha-segura",
            email="admin@example.com",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            "/admin/profiles/forensicexaminersp/teams-by-nucleus/",
            {"nucleus_id": str(self.nucleus_americana.pk)},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        team_ids = {item["id"] for item in payload["teams"]}
        self.assertIn(str(self.team_limeira.pk), team_ids)
        self.assertNotIn(str(self.team_centro.pk), team_ids)
