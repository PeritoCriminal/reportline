"""
Rotas HTTP do app profiles.

Telas de perfil profissional do servidor pericial (SP).
"""

from django.urls import path

from profiles.views.forensic_examiner_sp_views import ForensicExaminerSPProfileView

app_name = "profiles"

urlpatterns = [
    path(
        "forensic-examiner-sp/",
        ForensicExaminerSPProfileView.as_view(),
        name="forensic_examiner_sp",
    ),
]
