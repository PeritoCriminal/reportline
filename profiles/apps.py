"""
Configuração do app profiles.

Concentra o perfil profissional do perito criminalístico de SP vinculado
ao usuário autenticado e à lotação em equipe pericial.
"""

from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """AppConfig do perfil profissional do perito criminal (SP)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "profiles"
    verbose_name = "Perfis profissionais"

    def ready(self):
        """Carrega registradores do admin modular."""
        import profiles.admin  # noqa: F401
