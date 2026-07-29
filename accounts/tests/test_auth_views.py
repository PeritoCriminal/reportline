"""
Testes das views de autenticação do app accounts.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class LoginViewTests(TestCase):
    """Testes da CBV de login com credenciais locais Django."""

    def setUp(self):
        """Cria usuário de teste para cenários de autenticação."""
        self.user = get_user_model().objects.create_user(
            username="perito1",
            password="senha-segura",
        )

    def test_login_page_renders_form(self):
        """Garante que a rota de login exibe o formulário em português."""
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrar no ReportLine")
        self.assertContains(response, "Usuário")
        self.assertContains(response, "Senha")

    @override_settings(
        AUTH_PROVIDER="google",
        GOOGLE_CLIENT_ID="test-client-id",
        GOOGLE_CLIENT_SECRET="test-client-secret",
    )
    def test_login_page_shows_google_button_when_enabled(self):
        """Garante botão Google quando AUTH_PROVIDER=google e credenciais existem."""
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "Entrar com Google")
        self.assertContains(response, "Entrar com administrador")
        self.assertNotContains(response, "operadores internos")

    @override_settings(
        AUTH_PROVIDER="local",
        GOOGLE_CLIENT_ID="",
        GOOGLE_CLIENT_SECRET="",
    )
    def test_login_page_hides_google_button_when_local_provider(self):
        """Garante ausência do botão Google na fase 0 (AUTH_PROVIDER=local)."""
        response = self.client.get(reverse("accounts:login"))
        self.assertNotContains(response, "Entrar com Google")

    def test_login_with_valid_credentials_redirects_to_home(self):
        """Garante login bem-sucedido com redirecionamento para a página inicial."""
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "perito1", "password": "senha-segura"},
        )
        self.assertRedirects(response, reverse("index"))

    def test_login_with_invalid_credentials_shows_error(self):
        """Garante mensagem em português quando credenciais são inválidas."""
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "perito1", "password": "senha-errada"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "entre com um usuário")
        self.assertContains(response, "senha corretos")

    def test_authenticated_user_is_redirected_from_login_page(self):
        """Garante que usuário já autenticado não veja o formulário novamente."""
        self.client.login(username="perito1", password="senha-segura")
        response = self.client.get(reverse("accounts:login"))
        self.assertRedirects(response, reverse("index"))


class LogoutViewTests(TestCase):
    """Testes da CBV de logout."""

    def setUp(self):
        """Cria e autentica usuário para testes de encerramento de sessão."""
        self.user = get_user_model().objects.create_user(
            username="perito1",
            password="senha-segura",
        )
        self.client.login(username="perito1", password="senha-segura")

    def test_logout_ends_session_and_redirects_to_login(self):
        """Garante que logout encerre a sessão e redirecione para login."""
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))

        home_response = self.client.get(reverse("index"))
        self.assertFalse(home_response.wsgi_request.user.is_authenticated)
