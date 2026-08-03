"""
Rotas HTTP do fluxo de laudo pericial do IC-SP.
"""

from django.urls import path

from institution_ic_sp.forensic_report.common.views.case_intake_views import CaseIntakeView

urlpatterns = [
    path("", CaseIntakeView.as_view(), name="intake"),
]
