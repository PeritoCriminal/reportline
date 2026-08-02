"""
API JSON para layout de página do relatório (cabeçalho e rodapé).
"""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views import View

from reports.services.report_editor_context import (
    render_page_footer_html,
    render_page_header_html,
)
from reports.services.report_page_layout import (
    apply_footer_template,
    apply_header_template,
    clear_band_logo_cell,
    merge_page_layout,
    normalize_page_layout,
    update_footer_logo_cell_from_image,
    update_logo_cell_from_image,
)
from reports.services.report_page_layout_image_cleanup import (
    delete_removed_page_layout_images,
)
from reports.services.report_user_page_layout import sync_user_page_layout_preferences
from reports.views.report_node_api_views import ReportAuthorMixin, _validation_error_response


class ReportPageLayoutView(ReportAuthorMixin, View):
    """Atualiza cabeçalho, rodapé e layout de página via PATCH."""

    def patch(self, request, pk):
        """Persiste layout de página e retorna HTML atualizado das faixas."""
        report = self.get_report()

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        section = payload.get("section", "header")
        band = section if section in ("header", "footer") else "header"
        old_layout = report.page_layout

        try:
            if payload.get("apply_template"):
                template_id = payload.get("template_id")
                if not template_id:
                    raise ValidationError("Informe template_id.")
                if band == "footer":
                    page_layout = apply_footer_template(report.page_layout, template_id)
                else:
                    page_layout = apply_header_template(report.page_layout, template_id)
            elif payload.get("clear_logo_cell") is not None:
                cell_index = int(payload.get("clear_logo_cell"))
                page_layout = clear_band_logo_cell(
                    report.page_layout,
                    band=band,
                    cell_index=cell_index,
                )
            elif payload.get("update_logo_cell") is not None:
                cell_index = int(payload.get("update_logo_cell"))
                image_payload = payload.get("image")
                if not isinstance(image_payload, dict):
                    raise ValidationError("Informe image com metadados do upload.")
                if band == "footer":
                    page_layout = update_footer_logo_cell_from_image(
                        report.page_layout,
                        cell_index=cell_index,
                        image_payload=image_payload,
                    )
                else:
                    page_layout = update_logo_cell_from_image(
                        report.page_layout,
                        cell_index=cell_index,
                        image_payload=image_payload,
                    )
            else:
                incoming = payload.get("page_layout", payload)
                page_layout = merge_page_layout(report.page_layout, incoming)

            delete_removed_page_layout_images(old_layout, page_layout)
            report.page_layout = page_layout
            report.save(update_fields=["page_layout", "updated_at"])
            if report.author_id:
                sync_user_page_layout_preferences(report.author, page_layout)
        except ValidationError as exc:
            return _validation_error_response(exc)

        normalized = normalize_page_layout(report.page_layout)
        header_html = render_page_header_html(normalized, request)
        footer_html = render_page_footer_html(normalized, request)
        return JsonResponse(
            {
                "page_layout": normalized,
                "html": header_html,
                "header_html": header_html,
                "footer_html": footer_html,
            }
        )

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["PATCH"])
