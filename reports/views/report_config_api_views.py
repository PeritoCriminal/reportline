# reportline/reports/views/report_config_api_views.py
"""
API JSON para configuração do laudo e preferências do usuário.
"""

from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views import View

from reports.services.report_config import build_config_refresh_payload, update_report_config
from reports.services.report_editor_context import render_outline_refresh_payload
from reports.services.report_user_config import serialize_report_config
from reports.views.report_node_api_views import ReportAuthorMixin, _validation_error_response


class ReportConfigView(ReportAuthorMixin, View):
    """Consulta e atualiza configuração do laudo aberto e defaults do usuário."""

    def get(self, request, pk):
        """Retorna configuração persistida do laudo atual."""
        report = self.get_report()
        payload = serialize_report_config(report)
        payload.update(build_config_refresh_payload(report))
        return JsonResponse(payload)

    def patch(self, request, pk):
        """Persiste configuração no laudo, no usuário e aplica efeitos no documento."""
        report = self.get_report()

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        try:
            if "number_headings" not in payload:
                raise ValidationError("Informe number_headings.")
            if "number_captions" not in payload:
                raise ValidationError("Informe number_captions.")
            if "first_line_indent" not in payload:
                raise ValidationError("Informe first_line_indent.")

            data = update_report_config(
                report,
                request.user,
                number_headings=bool(payload["number_headings"]),
                number_captions=bool(payload["number_captions"]),
                first_line_indent=bool(payload["first_line_indent"]),
            )
            outline_payload = render_outline_refresh_payload(report, request)
            data["outline_html"] = outline_payload["html"]
            data["heading_numbers"] = outline_payload["heading_numbers"]
        except ValidationError as exc:
            return _validation_error_response(exc)

        return JsonResponse(data)

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        return HttpResponseNotAllowed(["GET", "PATCH"])
