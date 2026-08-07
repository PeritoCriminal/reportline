# reportline/institution_ic_sp/apps.py
"""
Configuração do app institution_ic_sp.

Mantém dados institucionais provisórios do IC-SP para uso durante
o desenvolvimento do ReportLine.
"""

from django.apps import AppConfig


class InstitutionIcSpConfig(AppConfig):
    """AppConfig do cadastro institucional provisório do IC-SP."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "institution_ic_sp"
    verbose_name = "Instituição IC-SP (provisório)"

    def ready(self):
        """Carrega registradores do admin modular."""
        import institution_ic_sp.admin  # noqa: F401
