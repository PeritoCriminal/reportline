"""
Rotas HTTP do app reports.

Telas de criação e edição de relatórios modulares.
"""

from django.urls import path

from reports.views.report_create_views import ReportCreateView
from reports.views.report_editor_views import ReportEditorView

app_name = "reports"

urlpatterns = [
    path(
        "new/",
        ReportCreateView.as_view(),
        name="new",
    ),
    path(
        "<uuid:pk>/edit/",
        ReportEditorView.as_view(),
        name="edit",
    ),
]
