"""
Rotas HTTP do app reports.

Telas de criação e edição de relatórios modulares.
"""

from django.urls import path

from reports.views.report_create_views import ReportCreateView
from reports.views.report_editor_views import ReportEditorOutlineView, ReportEditorView
from reports.views.report_list_views import ReportListView
from reports.views.report_node_api_views import (
    ReportNodeCreateView,
    ReportNodeDetailView,
    ReportNodeReorderView,
)

app_name = "reports"

urlpatterns = [
    path(
        "",
        ReportListView.as_view(),
        name="list",
    ),
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
    path(
        "<uuid:pk>/outline/",
        ReportEditorOutlineView.as_view(),
        name="outline",
    ),
    path(
        "<uuid:pk>/nodes/",
        ReportNodeCreateView.as_view(),
        name="node_create",
    ),
    path(
        "<uuid:pk>/nodes/reorder/",
        ReportNodeReorderView.as_view(),
        name="node_reorder",
    ),
    path(
        "<uuid:pk>/nodes/<uuid:node_id>/",
        ReportNodeDetailView.as_view(),
        name="node_update",
    ),
]
