"""
Rotas HTTP do app institution_ic_sp.

Inclui o fluxo de laudo pericial para servidores com perfil ForensicExaminerSP.
"""

from django.urls import include, path

app_name = "institution_ic_sp"

urlpatterns = [
    path(
        "forensic-report/",
        include(
            ("institution_ic_sp.forensic_report.urls", "forensic_report"),
            namespace="forensic_report",
        ),
    ),
]
