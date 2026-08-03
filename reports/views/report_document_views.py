"""
Views de renderização de leitura do relatório.

Concentra CBVs de preview HTML e, futuramente, exportação PDF.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView

from reports.models import Report
from reports.services.report_document_context import build_report_document_context


class ReportDocumentPreviewView(LoginRequiredMixin, DetailView):
    """
    Visualização read-only do laudo completo para o autor.

    Renderiza HTML autônomo com estilos inline embutidos, espelhando a ordem
    de leitura do corpo do editor sem ``contenteditable``.
    """

    model = Report
    template_name = "reports/document/report_document.html"
    context_object_name = "report"

    def get_queryset(self):
        """Restringe preview aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user)

    def get_context_data(self, **kwargs):
        """Monta seções sanitizadas e CSS inline para o template de documento."""
        context = super().get_context_data(**kwargs)
        context.update(build_report_document_context(self.object, self.request))
        return context
