"""
Views de edição de relatórios modulares.

Concentra CBVs da interface de composição por blocos tipados.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import DetailView

from reports.models import Report
from reports.services.report_editor_bootstrap import ensure_editor_bootstrap
from reports.services.report_editor_context import (
    build_report_editor_context,
    render_outline_refresh_payload,
)
from reports.services.report_image_processing import MAX_IMAGE_SIDE_PX
from reports.views.report_node_api_views import ReportAuthorMixin


class ReportEditorView(LoginRequiredMixin, DetailView):
    """
    Tela de edição visual de um relatório pertencente ao usuário autenticado.

    Garante bootstrap com título H1 vazio quando necessário e carrega
    sumário e corpo editável para os partials do template.
    """

    model = Report
    template_name = "reports/report_editor.html"
    context_object_name = "report"

    def get_queryset(self):
        """Restringe edição aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user)

    def get_object(self, queryset=None):
        """Aplica bootstrap de editor antes de renderizar relatório vazio."""
        report = super().get_object(queryset)
        self._bootstrapped_node = ensure_editor_bootstrap(report)
        return report

    def get_context_data(self, **kwargs):
        """Enriquece o contexto com estruturas de sumário e corpo do editor."""
        context = super().get_context_data(**kwargs)
        context.update(build_report_editor_context(self.object))
        context["autofocus_node_id"] = (
            self._bootstrapped_node.pk if self._bootstrapped_node else None
        )
        context["max_image_side_px"] = MAX_IMAGE_SIDE_PX
        return context


class ReportEditorOutlineView(ReportAuthorMixin, View):
    """Retorna HTML atualizado do sumário lateral do editor (GET)."""

    def get(self, request, pk):
        """Serializa partial do sumário após alterações no documento."""
        report = self.get_report()
        payload = render_outline_refresh_payload(report, request)
        return JsonResponse(payload)

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        from django.http import HttpResponseNotAllowed

        return HttpResponseNotAllowed(["GET"])
