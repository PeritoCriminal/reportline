"""Configuração do app common."""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Registra utilitários compartilhados entre apps do ReportLine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "common"
    verbose_name = "Common"

    def ready(self) -> None:
        """Aplica branding do admin na inicialização do projeto."""
        from common.admin_site import configure_admin_site

        configure_admin_site()
