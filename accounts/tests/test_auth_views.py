"""
Testes das views de autenticação do app accounts.
"""

from django.test import TestCase
from django.urls import reverse


class LoginViewTests(TestCase):
    """Testes da CBV provisória de login."""

    def test_login_returns_200(self):
        """Garante que a rota de login responde com sucesso."""
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)

    def test_login_displays_portuguese_placeholder_message(self):
        """Garante que a mensagem provisória esteja em português para o usuário."""
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "Tela de Login em desenvolvimento.")
