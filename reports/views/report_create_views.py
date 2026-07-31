"""
Views de criação de relatórios modulares.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView

from common.user_messages import notify_success
from reports.forms.report_form import ReportCreateForm
from reports.models import Report
from reports.services.report_creation import create_report


class ReportCreateView(LoginRequiredMixin, CreateView):
    """
    Formulário para iniciar um relatório em rascunho.

    Após a criação, redireciona o autor para o editor visual do documento.
    """

    model = Report
    form_class = ReportCreateForm
    template_name = "reports/report_form.html"

    def form_valid(self, form):
        """Persiste o relatório via serviço e encaminha ao editor."""
        self.object = create_report(
            author=self.request.user,
            title=form.cleaned_data["title"],
        )
        notify_success(self.request, "Relatório criado com sucesso.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        """Abre o editor do relatório recém-criado."""
        return reverse("reports:edit", kwargs={"pk": self.object.pk})
