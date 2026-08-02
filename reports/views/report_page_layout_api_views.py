"""
API JSON para layout de página do relatório (cabeçalho).
"""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views import View

from reports.services.report_editor_context import render_page_header_html
from reports.services.report_page_layout import (
    apply_header_template,
    normalize_page_layout,
    update_logo_cell_from_image,
)
from reports.views.report_node_api_views import ReportAuthorMixin, _validation_error_response


class ReportPageLayoutView(ReportAuthorMixin, View):
    """Atualiza cabeçalho e layout de página via PATCH."""

    def patch(self, request, pk):
        """Persiste layout de página e retorna HTML atualizado do cabeçalho."""
        report = self.get_report()

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        try:
            if payload.get("apply_template"):
                template_id = payload.get("template_id")
                if not template_id:
                    raise ValidationError("Informe template_id.")
                page_layout = apply_header_template(report.page_layout, template_id)
            elif payload.get("update_logo_cell") is not None:
                cell_index = int(payload.get("update_logo_cell"))
                image_payload = payload.get("image")
                if not isinstance(image_payload, dict):
                    raise ValidationError("Informe image com metadados do upload.")
                page_layout = update_logo_cell_from_image(
                    report.page_layout,
                    cell_index=cell_index,
                    image_payload=image_payload,
                )
            else:
                page_layout = normalize_page_layout(payload.get("page_layout", payload))

            report.page_layout = page_layout
            report.save(update_fields=["page_layout", "updated_at"])
        except ValidationError as exc:
            return _validation_error_response(exc)

        normalized = normalize_page_layout(report.page_layout)
        return JsonResponse(
            {
                "page_layout": normalized,
                "html": render_page_header_html(normalized, request),
            }
        )

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["PATCH"])
