# reportline/reports/views/report_document_views.py
"""
Views de renderização de leitura do relatório.

Concentra CBVs de preview HTML e exportação PDF.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView

from reports.models import Report
from reports.services.report_document_context import build_report_document_context
from reports.services.report_document_pdf import (
    build_report_document_html,
    pdf_download_filename,
    render_report_document_pdf_bytes,
)
from reports.services.report_document_pdf_fragments import ReportPdfUnavailable


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


class ReportDocumentPdfView(LoginRequiredMixin, DetailView):
    """
    Exportação PDF do laudo para o autor.

    Suporta ``?html=1`` para inspecionar o HTML enviado ao Chromium.
    """

    model = Report
    context_object_name = "report"

    def get_queryset(self):
        """Restringe exportação aos relatórios cujo autor é o usuário da sessão."""
        return Report.objects.filter(author=self.request.user)

    def get(self, request, *args, **kwargs):
        """Retorna PDF inline, HTML de debug ou página 503 quando indisponível."""
        self.object = self.get_object()

        if request.GET.get("html") == "1":
            html = build_report_document_html(self.object, request)
            return HttpResponse(html, content_type="text/html; charset=utf-8")

        try:
            pdf_bytes = render_report_document_pdf_bytes(self.object, request)
        except ReportPdfUnavailable:
            return render(
                request,
                "reports/document/unavailable.html",
                {"report": self.object},
                status=503,
            )

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="{pdf_download_filename(self.object)}"'
        )
        return response
