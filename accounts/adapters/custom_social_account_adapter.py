"""
Adapter django-allauth para login social OAuth.

Delega provisionamento de CustomUser ao serviço compartilhado de OAuth,
permitindo reutilização na integração gov.br (fase 2).
"""

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect

from accounts.services.oauth_user_service import (
    InactiveOAuthUserError,
    OAuthUserClaims,
    normalize_provider,
    provision_oauth_user,
)
from common.user_messages import notify_error


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Integra django-allauth ao serviço de provisionamento OAuth do ReportLine."""

    def pre_social_login(self, request, sociallogin):
        """
        Vincula conta existente por e-mail ou bloqueia usuários inativos.

        Raises:
            ImmediateHttpResponse: redireciona para login com mensagem em português.
        """
        if sociallogin.is_existing:
            if not sociallogin.user.is_active:
                notify_error(request, "Esta conta está desativada.")
                raise ImmediateHttpResponse(redirect("accounts:login"))
            return

        email = self._extract_email(sociallogin)
        if not email:
            return

        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        if not user.is_active:
            notify_error(request, "Esta conta está desativada.")
            raise ImmediateHttpResponse(redirect("accounts:login"))

        sociallogin.connect(request, user)

    def save_user(self, request, sociallogin, form=None):
        """Persiste usuário via serviço de provisionamento OAuth."""
        claims = self._build_claims(sociallogin)
        try:
            user = provision_oauth_user(claims)
        except InactiveOAuthUserError:
            notify_error(request, "Esta conta está desativada.")
            raise ImmediateHttpResponse(redirect("accounts:login")) from None

        sociallogin.user = user
        return user

    def _build_claims(self, sociallogin) -> OAuthUserClaims:
        """Monta claims normalizados a partir do sociallogin do allauth."""
        extra_data = sociallogin.account.extra_data or {}
        return OAuthUserClaims(
            provider=normalize_provider(sociallogin.account.provider),
            external_subject=sociallogin.account.uid,
            email=self._extract_email(sociallogin) or "",
            first_name=sociallogin.user.first_name or extra_data.get("given_name", ""),
            last_name=sociallogin.user.last_name or extra_data.get("family_name", ""),
        )

    def _extract_email(self, sociallogin) -> str | None:
        """Obtém o e-mail principal retornado pelo provedor social."""
        if sociallogin.user.email:
            return sociallogin.user.email

        for email_address in sociallogin.email_addresses:
            if email_address.email:
                return email_address.email

        extra_data = sociallogin.account.extra_data or {}
        return extra_data.get("email")
