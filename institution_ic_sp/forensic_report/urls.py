"""
Rotas HTTP do fluxo de laudo pericial do IC-SP.
"""

from django.urls import path

from institution_ic_sp.forensic_report.common.views.analyze_documents_views import (
    AnalyzeDocumentsView,
)
from institution_ic_sp.forensic_report.common.views.case_intake_views import (
    CaseIntakeQuickShellView,
    CaseIntakeView,
)

urlpatterns = [
    path("", CaseIntakeView.as_view(), name="intake"),
    path("quick-shell/", CaseIntakeQuickShellView.as_view(), name="quick_shell"),
    path(
        "analyze-documents/",
        AnalyzeDocumentsView.as_view(),
        name="analyze_documents",
    ),
]
