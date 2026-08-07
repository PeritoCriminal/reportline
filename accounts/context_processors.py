# reportline/accounts/context_processors.py
"""
Context processors do app accounts.

Expõe configurações de autenticação aos templates.
"""

from django.conf import settings


def auth_settings(request):
    """Disponibiliza flags de provedor OAuth para templates."""
    google_login_enabled = (
        settings.AUTH_PROVIDER == "google"
        and bool(settings.GOOGLE_CLIENT_ID)
        and bool(settings.GOOGLE_CLIENT_SECRET)
    )
    google_login_misconfigured = (
        settings.AUTH_PROVIDER == "google" and not google_login_enabled
    )
    return {
        "auth_provider": settings.AUTH_PROVIDER,
        "google_login_enabled": google_login_enabled,
        "google_login_misconfigured": google_login_misconfigured,
    }
