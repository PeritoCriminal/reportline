# reportline/common/admin_site.py
"""
Configuração de branding e textos do Django Admin do ReportLine.
"""

from django.contrib import admin


def configure_admin_site() -> None:
    """
    Aplica títulos e rótulos administrativos alinhados ao ReportLine.

    Deve ser invocado na inicialização do app ``common`` para garantir
    que todos os registradores herdem a mesma identidade visual.
    """
    admin.site.site_header = "Administração do Sistema ReportLine"
    admin.site.site_title = "ReportLine"
    admin.site.index_title = "Painel administrativo"
