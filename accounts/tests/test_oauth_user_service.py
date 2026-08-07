# reportline/accounts/tests/test_oauth_user_service.py
"""
Testes do serviço de provisionamento OAuth do app accounts.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models.custom_user import AuthProvider
from accounts.services.oauth_user_service import (
    InactiveOAuthUserError,
    OAuthUserClaims,
    normalize_provider,
    provision_oauth_user,
)

User = get_user_model()


class OAuthUserServiceTests(TestCase):
    """Testes de criação e atualização de CustomUser via claims OAuth."""

    def test_provision_creates_google_user(self):
        """Garante criação de usuário OAuth com provedor Google e senha inutilizável."""
        user = provision_oauth_user(
            OAuthUserClaims(
                provider=AuthProvider.GOOGLE,
                external_subject="google-sub-123",
                email="perito@example.com",
                first_name="João",
                last_name="Silva",
            )
        )

        self.assertEqual(user.auth_provider, AuthProvider.GOOGLE)
        self.assertEqual(user.external_subject, "google-sub-123")
        self.assertEqual(user.email, "perito@example.com")
        self.assertEqual(user.first_name, "João")
        self.assertFalse(user.has_usable_password())

    def test_provision_updates_existing_user_by_external_subject(self):
        """Garante atualização de perfil quando o identificador externo já existe."""
        existing = User.objects.create_user(
            username="perito1",
            email="perito@example.com",
            password="senha-segura",
            auth_provider=AuthProvider.GOOGLE,
            external_subject="google-sub-123",
            first_name="Antigo",
        )

        user = provision_oauth_user(
            OAuthUserClaims(
                provider=AuthProvider.GOOGLE,
                external_subject="google-sub-123",
                email="perito@example.com",
                first_name="Atualizado",
                last_name="Silva",
            )
        )

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.first_name, "Atualizado")
        self.assertEqual(user.last_name, "Silva")

    def test_provision_links_existing_local_user_by_email(self):
        """Garante vinculação de conta local existente pelo e-mail no primeiro login Google."""
        existing = User.objects.create_user(
            username="perito_local",
            email="perito@example.com",
            password="senha-segura",
        )

        user = provision_oauth_user(
            OAuthUserClaims(
                provider=AuthProvider.GOOGLE,
                external_subject="google-sub-456",
                email="perito@example.com",
            )
        )

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.auth_provider, AuthProvider.GOOGLE)
        self.assertEqual(user.external_subject, "google-sub-456")

    def test_provision_rejects_inactive_user(self):
        """Garante bloqueio de login OAuth para conta desativada."""
        User.objects.create_user(
            username="inativo",
            email="inativo@example.com",
            password="senha-segura",
            is_active=False,
        )

        with self.assertRaises(InactiveOAuthUserError):
            provision_oauth_user(
                OAuthUserClaims(
                    provider=AuthProvider.GOOGLE,
                    external_subject="google-sub-inativo",
                    email="inativo@example.com",
                )
            )

    def test_normalize_provider_maps_google_alias(self):
        """Garante normalização do identificador de provedor Google."""
        self.assertEqual(normalize_provider("google"), AuthProvider.GOOGLE)
