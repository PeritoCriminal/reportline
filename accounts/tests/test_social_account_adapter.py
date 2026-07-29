"""
Testes do adapter social django-allauth do app accounts.
"""

from types import SimpleNamespace
from unittest.mock import patch

from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from accounts.adapters.custom_social_account_adapter import CustomSocialAccountAdapter
from accounts.models.custom_user import AuthProvider
from accounts.services.oauth_user_service import InactiveOAuthUserError, OAuthUserClaims

User = get_user_model()


def _attach_session_and_messages(request):
    """Anexa sessão e storage de mensagens ao request de teste."""
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)


class CustomSocialAccountAdapterTests(TestCase):
    """Testes do adapter que delega provisionamento OAuth ao serviço central."""

    def setUp(self):
        """Prepara request factory e adapter para os cenários de callback."""
        self.factory = RequestFactory()
        self.adapter = CustomSocialAccountAdapter()
        self.request = self.factory.get("/accounts/social/google/login/callback/")
        _attach_session_and_messages(self.request)

    def _build_sociallogin(self, email="perito@example.com", uid="google-sub-789"):
        """Monta objeto mínimo compatível com django-allauth."""
        user = User(email=email, first_name="Maria", last_name="Souza")
        account = SimpleNamespace(
            provider="google",
            uid=uid,
            extra_data={"email": email, "given_name": "Maria", "family_name": "Souza"},
        )
        email_address = SimpleNamespace(email=email)
        sociallogin = SimpleNamespace(
            is_existing=False,
            user=user,
            account=account,
            email_addresses=[email_address],
        )
        return sociallogin

    @patch("accounts.adapters.custom_social_account_adapter.provision_oauth_user")
    def test_save_user_delegates_to_provision_service(self, mock_provision):
        """Garante que o adapter use o serviço central de provisionamento OAuth."""
        provisioned = User.objects.create_user(
            username="perito_oauth",
            email="perito@example.com",
            password="senha-segura",
            auth_provider=AuthProvider.GOOGLE,
            external_subject="google-sub-789",
        )
        mock_provision.return_value = provisioned
        sociallogin = self._build_sociallogin()

        user = self.adapter.save_user(self.request, sociallogin)

        mock_provision.assert_called_once()
        claims = mock_provision.call_args.args[0]
        self.assertIsInstance(claims, OAuthUserClaims)
        self.assertEqual(claims.provider, AuthProvider.GOOGLE)
        self.assertEqual(user, provisioned)
        self.assertEqual(sociallogin.user, provisioned)

    @patch("accounts.adapters.custom_social_account_adapter.provision_oauth_user")
    def test_save_user_redirects_when_account_is_inactive(self, mock_provision):
        """Garante redirecionamento ao login quando o serviço detecta conta inativa."""
        mock_provision.side_effect = InactiveOAuthUserError()
        sociallogin = self._build_sociallogin()

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.save_user(self.request, sociallogin)

        stored = list(get_messages(self.request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Esta conta está desativada.")
        self.assertIn("error", stored[0].tags)

    def test_pre_social_login_connects_existing_user_by_email(self):
        """Garante vinculação automática quando o e-mail já existe localmente."""
        existing = User.objects.create_user(
            username="perito_local",
            email="perito@example.com",
            password="senha-segura",
        )
        sociallogin = self._build_sociallogin()
        sociallogin.connect = lambda request, user: setattr(sociallogin, "user", user)

        self.adapter.pre_social_login(self.request, sociallogin)

        self.assertEqual(sociallogin.user.pk, existing.pk)

    def test_pre_social_login_blocks_inactive_existing_social_user(self):
        """Garante bloqueio quando usuário social existente está inativo."""
        inactive = User.objects.create_user(
            username="inativo",
            email="inativo@example.com",
            password="senha-segura",
            is_active=False,
        )
        sociallogin = SimpleNamespace(is_existing=True, user=inactive)

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, sociallogin)

        stored = list(get_messages(self.request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Esta conta está desativada.")

    def test_pre_social_login_blocks_inactive_existing_user_by_email(self):
        """Garante bloqueio e mensagem quando e-mail local existente está inativo."""
        User.objects.create_user(
            username="inativo_local",
            email="perito@example.com",
            password="senha-segura",
            is_active=False,
        )
        sociallogin = self._build_sociallogin()

        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, sociallogin)

        stored = list(get_messages(self.request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Esta conta está desativada.")
