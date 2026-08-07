# reportline/accounts/services/oauth_user_service.py
"""
Serviço de provisionamento de CustomUser a partir de claims OAuth.

Centraliza criação e atualização de usuários para provedores sociais (Google)
e futuros backends OIDC (gov.br), conforme ADR-0003.
"""

import re
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from accounts.models.custom_user import AuthProvider

User = get_user_model()


class InactiveOAuthUserError(Exception):
    """Indica tentativa de login OAuth com conta desativada."""


@dataclass(frozen=True)
class OAuthUserClaims:
    """Claims normalizados de um provedor OAuth/OIDC."""

    provider: str
    external_subject: str
    email: str
    first_name: str = ""
    last_name: str = ""


def provision_oauth_user(claims: OAuthUserClaims):
    """
    Cria ou atualiza um CustomUser a partir de claims OAuth normalizados.

    Prioriza correspondência por provedor + identificador externo; em seguida,
    vincula por e-mail quando o usuário já existir localmente.

    Raises:
        InactiveOAuthUserError: se a conta encontrada estiver inativa.
        ValueError: se e-mail ou identificador externo estiverem ausentes.
    """
    if not claims.external_subject:
        raise ValueError("Identificador externo OAuth é obrigatório.")
    if not claims.email:
        raise ValueError("E-mail OAuth é obrigatório.")

    user = User.objects.filter(
        auth_provider=claims.provider,
        external_subject=claims.external_subject,
    ).first()

    if user is None:
        user = User.objects.filter(email__iexact=claims.email).first()
        if user is not None:
            user.auth_provider = claims.provider
            user.external_subject = claims.external_subject

    if user is None:
        user = User(
            username=_build_unique_username(claims.email),
            email=claims.email,
            auth_provider=claims.provider,
            external_subject=claims.external_subject,
        )
        user.set_unusable_password()

    if not user.is_active:
        raise InactiveOAuthUserError()

    user.first_name = claims.first_name or user.first_name
    user.last_name = claims.last_name or user.last_name
    user.email = claims.email
    user.save()
    return user


def _build_unique_username(email: str) -> str:
    """Gera username único a partir do e-mail OAuth."""
    local_part = email.split("@", maxsplit=1)[0]
    base = re.sub(r"[^\w.@+-]", "", local_part)[:140] or "usuario"
    username = base
    counter = 1

    while User.objects.filter(username=username).exists():
        suffix = f"_{counter}"
        username = f"{base[: 150 - len(suffix)]}{suffix}"
        counter += 1

    return username


def normalize_provider(provider: str) -> str:
    """Normaliza identificador de provedor para valores de AuthProvider."""
    provider_map = {
        "google": AuthProvider.GOOGLE,
        "govbr": AuthProvider.GOVBR,
        "gov.br": AuthProvider.GOVBR,
    }
    return provider_map.get(provider, provider)
