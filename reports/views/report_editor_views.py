"""
Views de edição de relatórios modulares.

Concentra CBVs da interface de composição por blocos tipados.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from reports.models import Report
from reports.services.report_editor_context import build_report_editor_context


class ReportEditorView(LoginRequiredMixin, DetailView):
    """
    Tela de edição visual de um relatório pertencente ao usuário autenticado.

    Carrega sumário em árvore e sequência de blocos do corpo para os
    partials do template; persistência interativa será adicionada em fase posterior.
    """

    model = Report
    template_name = "reports/report_editor.html"
    context_object_name = "report"

    def get_queryset(self):
        """Restringe edição aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user)

    def get_context_data(self, **kwargs):
        """Enriquece o contexto com estruturas de sumário e corpo do editor."""
        context = super().get_context_data(**kwargs)
        context.update(build_report_editor_context(self.object))
        return context
