"""
Testes do intake de laudo pericial do IC-SP.
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from institution_ic_sp.models import ForensicTeam
from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from reports.models import Report, ReportBlockType
from reports.services.report_kind import is_forensic_report

User = get_user_model()


class ForensicReportIntakeViewTests(TestCase):
    """Testes da view de intake comum de laudo pericial."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e equipe pericial."""
        cls.team = ForensicTeam.objects.get(code="EPC-SPC")
        cls.examiner_user = User.objects.create_user(
            username="perito_intake",
            password="senha-segura",
        )
        cls.regular_user = User.objects.create_user(
            username="comum1",
            password="senha-segura",
        )
        ForensicExaminerSP.objects.create(
            user=cls.examiner_user,
            forensic_team=cls.team,
            display_name="Dr. Intake",
            job_title=ForensicJobTitle.PERITO_CRIMINAL,
            calling_gender=GenderCalling.MALE,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes."""
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('institution_ic_sp:forensic_report:intake')}",
        )

    def test_user_without_profile_receives_404(self):
        """Garante 404 para usuário autenticado sem ForensicExaminerSP."""
        self.client.login(username="comum1", password="senha-segura")
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))
        self.assertEqual(response.status_code, 404)

    def test_intake_prefills_examiner_name(self):
        """Garante pré-preenchimento do campo Perito com display_name do perfil."""
        self.client.login(username="perito_intake", password="senha-segura")
        response = self.client.get(reverse("institution_ic_sp:forensic_report:intake"))
        self.assertContains(response, 'value="Dr. Intake"')

    def test_examiner_can_generate_forensic_report(self):
        """Garante geração de laudo pericial e redirecionamento ao editor."""
        self.client.login(username="perito_intake", password="senha-segura")
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:intake"),
            {
                "manual_submit": "1",
                "report_number": "7",
                "report_year": "2026",
                "designation_date": "2026-03-01",
                "requesting_authority": "Dr. Delegado",
                "occurrence_report": "BO-1",
                "attendance_protocol": "2026/0007",
                "examiner": "Dr. Intake",
                "exam_objective": "Examinar local.",
                "supplementary_prompt": "Prioridade alta.",
            },
        )

        report = Report.objects.get(author=self.examiner_user)
        self.assertRedirects(response, reverse("reports:edit", kwargs={"pk": report.pk}))
        self.assertTrue(is_forensic_report(report))
        self.assertTrue(
            report.nodes.filter(block__block_type=ReportBlockType.UNORDERED_LIST).exists()
        )

    def test_missing_report_number_shows_inline_error(self):
        """Garante erro inline quando número do laudo não é informado."""
        self.client.login(username="perito_intake", password="senha-segura")
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:intake"),
            {
                "manual_submit": "1",
                "report_number": "",
                "report_year": "2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório")
        self.assertEqual(Report.objects.filter(author=self.examiner_user).count(), 0)

    def test_intake_accepts_document_upload_without_persisting(self):
        """Garante que upload de documento não impede geração do laudo."""
        self.client.login(username="perito_intake", password="senha-segura")
        upload = SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 stub",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("institution_ic_sp:forensic_report:intake"),
            {
                "manual_submit": "1",
                "report_number": "8",
                "report_year": "2026",
                "documents": upload,
            },
        )

        report = Report.objects.get(author=self.examiner_user)
        self.assertRedirects(response, reverse("reports:edit", kwargs={"pk": report.pk}))
