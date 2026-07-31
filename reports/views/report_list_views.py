"""
Views de listagem de relatórios modulares.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from reports.models import Report


class ReportListView(LoginRequiredMixin, ListView):
    """
    Lista relatórios do usuário autenticado em ordem cronológica inversa.

    Cada item encaminha ao editor visual do documento selecionado.
    """

    model = Report
    template_name = "reports/report_list.html"
    context_object_name = "reports"
    paginate_by = 20

    def get_queryset(self):
        """Restringe listagem aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user).order_by("-created_at")
