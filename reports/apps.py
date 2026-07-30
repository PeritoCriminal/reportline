"""
Configuração do app reports.

Concentra relatórios modulares, a árvore de nós de composição e os blocos
genéricos de conteúdo reutilizáveis entre tipos de documento.
"""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """AppConfig de relatórios modulares e blocos de conteúdo."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"
    verbose_name = "Relatórios"

    def ready(self):
        """Carrega registradores do admin modular e sinais de integridade."""
        import reports.admin  # noqa: F401
        import reports.signals  # noqa: F401
