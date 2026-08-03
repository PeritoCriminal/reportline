"""
Views de exclusão de relatórios modulares.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import DeleteView

from common.user_messages import notify_success
from reports.models import Report
from reports.services.report_deletion import delete_report


class ReportDeleteView(LoginRequiredMixin, DeleteView):
    """
    Confirma e executa exclusão permanente de um laudo do autor autenticado.

    A tela de confirmação alerta sobre perda irreversível de nós, blocos
    e arquivos de imagem antes do POST definitivo.
    """

    model = Report
    template_name = "reports/report_confirm_delete.html"
    context_object_name = "report"
    success_url = reverse_lazy("reports:list")

    def get_queryset(self):
        """Restringe exclusão aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user)

    def form_valid(self, form):
        """Remove laudo e recursos associados, exibindo feedback de sucesso."""
        delete_report(self.object)
        notify_success(self.request, "Relatório excluído com sucesso.")
        return HttpResponseRedirect(self.get_success_url())
