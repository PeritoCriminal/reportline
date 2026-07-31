"""
Testes da view de listagem de relatórios.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Report, ReportStatus

User = get_user_model()


class ReportListViewTests(TestCase):
    """Testes da listagem de relatórios do autor autenticado."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e relatórios para os cenários."""
        cls.author = User.objects.create_user(
            username="lista_autor",
            password="senha-segura",
        )
        cls.other_user = User.objects.create_user(
            username="lista_outro",
            password="senha-segura",
        )
        cls.own_report = Report.objects.create(
            author=cls.author,
            title="Laudo próprio",
            status=ReportStatus.DRAFT,
        )
        Report.objects.create(
            author=cls.other_user,
            title="Laudo de outro usuário",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        """Garante redirecionamento ao login para visitantes não autenticados."""
        response = self.client.get(reverse("reports:list"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('reports:list')}",
        )

    def test_author_sees_only_own_reports(self):
        """Garante que o autor veja somente seus relatórios na listagem."""
        self.client.login(username="lista_autor", password="senha-segura")
        response = self.client.get(reverse("reports:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laudo próprio")
        self.assertNotContains(response, "Laudo de outro usuário")

    def test_author_sees_empty_state_without_reports(self):
        """Garante mensagem e CTA quando autor não possui relatórios."""
        User.objects.create_user(username="sem_laudos", password="senha-segura")
        self.client.login(username="sem_laudos", password="senha-segura")
        response = self.client.get(reverse("reports:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ainda não possui relatórios")
        self.assertContains(response, reverse("reports:new"))

    def test_index_shows_report_cards_for_authenticated_user(self):
        """Garante cards de relatórios na página inicial para usuário autenticado."""
        self.client.login(username="lista_autor", password="senha-segura")
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meus relatórios")
        self.assertContains(response, "Novo relatório")
        self.assertContains(response, reverse("reports:list"))
        self.assertContains(response, reverse("reports:new"))

    def test_index_shows_login_for_anonymous_user(self):
        """Garante CTA de login na página inicial para visitantes."""
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:login"))
        self.assertNotContains(response, "Meus relatórios")
