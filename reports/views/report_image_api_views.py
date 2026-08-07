# reportline/reports/views/report_image_api_views.py
"""
View JSON para upload de imagens no editor de relatório.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views import View

from reports.services.report_image_upload import (
    build_image_block_content,
    store_report_image,
)
from reports.views.report_node_api_views import ReportAuthorMixin, _validation_error_response


class ReportImageUploadView(ReportAuthorMixin, View):
    """Recebe arquivo multipart e retorna metadados para bloco de imagem."""

    def post(self, request, pk):
        """Processa upload, redimensiona e devolve payload de conteúdo."""
        report = self.get_report()
        uploaded_file = request.FILES.get("image")

        if not uploaded_file:
            return JsonResponse(
                {"errors": ["Selecione um arquivo de imagem."]},
                status=400,
            )

        try:
            report_image = store_report_image(report, uploaded_file)
        except ValidationError as exc:
            return _validation_error_response(exc)

        content = build_image_block_content(report_image)
        return JsonResponse(
            {
                "image_id": content["image_id"],
                "file": content["file"],
                "url": report_image.image.url,
                "width": content["width"],
                "height": content["height"],
                "alt": content["alt"],
            }
        )

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        return HttpResponseNotAllowed(["POST"])
