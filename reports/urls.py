"""
Rotas HTTP do app reports.

Telas de criação e edição de relatórios modulares.
"""

from django.urls import path

from reports.views.report_config_api_views import ReportConfigView
from reports.views.report_create_views import ReportCreateView
from reports.views.report_delete_views import ReportDeleteView
from reports.views.report_document_views import (
    ReportDocumentPdfView,
    ReportDocumentPreviewView,
)
from reports.views.report_editor_views import ReportEditorOutlineView, ReportEditorView
from reports.views.report_image_api_views import ReportImageUploadView
from reports.views.report_list_views import ReportListView
from reports.views.report_node_api_views import (
    ReportNodeCreateView,
    ReportNodeDetailView,
    ReportNodeReorderView,
)
from reports.views.report_page_layout_api_views import ReportPageLayoutView
from institution_ic_sp.forensic_report.views.forensic_bootstrap_api_views import (
    ForensicBootstrapAnalyzeView,
    ForensicBootstrapBuildView,
    ForensicBootstrapFinalizeView,
    ForensicBootstrapPromptView,
    ForensicBootstrapStatusView,
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
        "<uuid:pk>/config/",
        ReportConfigView.as_view(),
        name="config",
    ),
    path(
        "<uuid:pk>/edit/",
        ReportEditorView.as_view(),
        name="edit",
    ),
    path(
        "<uuid:pk>/delete/",
        ReportDeleteView.as_view(),
        name="delete",
    ),
    path(
        "<uuid:pk>/preview/",
        ReportDocumentPreviewView.as_view(),
        name="preview",
    ),
    path(
        "<uuid:pk>/document/",
        ReportDocumentPdfView.as_view(),
        name="document",
    ),
    path(
        "<uuid:pk>/outline/",
        ReportEditorOutlineView.as_view(),
        name="outline",
    ),
    path(
        "<uuid:pk>/images/upload/",
        ReportImageUploadView.as_view(),
        name="image_upload",
    ),
    path(
        "<uuid:pk>/page-layout/",
        ReportPageLayoutView.as_view(),
        name="page_layout",
    ),
    path(
        "<uuid:pk>/forensic-bootstrap/analyze/",
        ForensicBootstrapAnalyzeView.as_view(),
        name="forensic_bootstrap_analyze",
    ),
    path(
        "<uuid:pk>/forensic-bootstrap/build/",
        ForensicBootstrapBuildView.as_view(),
        name="forensic_bootstrap_build",
    ),
    path(
        "<uuid:pk>/forensic-bootstrap/status/",
        ForensicBootstrapStatusView.as_view(),
        name="forensic_bootstrap_status",
    ),
    path(
        "<uuid:pk>/forensic-bootstrap/prompt/",
        ForensicBootstrapPromptView.as_view(),
        name="forensic_bootstrap_prompt",
    ),
    path(
        "<uuid:pk>/forensic-bootstrap/finalize/",
        ForensicBootstrapFinalizeView.as_view(),
        name="forensic_bootstrap_finalize",
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
