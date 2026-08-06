"""
Testes da permissão de envio de imagens à IA externa no perfil do perito.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

User = get_user_model()


class ForensicExaminerExternalAiImagesTests(TestCase):
    """Testes do campo can_send_images_to_external_ai."""

    @classmethod
    def setUpTestData(cls):
        """Prepara perito com permissão desabilitada por padrão."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.user = User.objects.create_user(
            username="perito_imagens",
            password="senha-segura",
        )
        cls.examiner = ForensicExaminerSP.objects.create(
            user=cls.user,
            forensic_team=cls.team,
            display_name="Dr. Imagens",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_default_is_false(self):
        """Garante que novos perfis não enviam imagens à IA externa por padrão."""
        self.assertFalse(self.examiner.can_send_images_to_external_ai)

    def test_admin_can_enable(self):
        """Garante habilitação explícita pelo administrador."""
        self.examiner.can_send_images_to_external_ai = True
        self.examiner.save(update_fields=["can_send_images_to_external_ai"])
        self.examiner.refresh_from_db()
        self.assertTrue(self.examiner.can_send_images_to_external_ai)
