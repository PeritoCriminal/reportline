"""
API JSON do bootstrap interativo de laudos periciais no editor.
"""

from __future__ import annotations

import json
from dataclasses import replace

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.views import View

from institution_ic_sp.forensic_report.common.ai.client import is_ai_configured
from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads
from institution_ic_sp.forensic_report.common.services.case_metadata import normalize_case_metadata
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    analyze_case_metadata_from_documents,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.mixins import ForensicExaminerSPRequiredMixin
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    CRITICAL_PROMPT_FIELDS,
    STATE_ANALYZED,
    STATE_PROMPTING,
    STATE_READY,
    bootstrap_state,
    bootstrap_status_payload,
    compute_pending_prompts,
    mark_prompt_skipped,
    metadata_from_bootstrap,
    save_bootstrap_after_metadata_update,
    save_bootstrap_metadata,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_finalize import (
    finalize_bootstrap_prompts,
)
from institution_ic_sp.forensic_report.services.forensic_report_metadata_sync import (
    apply_prompt_field_value,
    sync_forensic_metadata_fields,
    validate_prompt_submit_value,
)
from institution_ic_sp.forensic_report.workflows.generic.services.report_draft_builder import (
    build_forensic_report_from_bootstrap,
)
from reports.models import Report
from reports.services.report_kind import is_forensic_report
from reports.views.report_node_api_views import _validation_error_response


class ForensicReportAuthorMixin(ForensicExaminerSPRequiredMixin):
    """Restringe operações de bootstrap ao autor do laudo pericial."""

    def get_report(self) -> Report:
        """Carrega laudo pericial pertencente ao usuário autenticado."""
        try:
            report = Report.objects.get(pk=self.kwargs["pk"], author=self.request.user)
        except Report.DoesNotExist as exc:
            raise Http404 from exc
        if not is_forensic_report(report):
            raise Http404
        return report


class ForensicBootstrapAnalyzeView(ForensicReportAuthorMixin, View):
    """Analisa documentos em memória e atualiza metadados do bootstrap."""

    def post(self, request, pk):
        """Processa uploads e persiste metadados inferidos no laudo."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state == STATE_READY:
            return JsonResponse(
                {"errors": ["Este laudo já foi montado."]},
                status=400,
            )

        uploaded_files = request.FILES.getlist("documents")
        if not uploaded_files:
            return HttpResponseBadRequest(
                json.dumps({"errors": ["Selecione ao menos um documento."]}),
                content_type="application/json",
            )

        manual = metadata_from_bootstrap(report.page_layout)
        examiner_name = (self.examiner_profile.display_name or "").strip()
        if not manual.examiner.strip() and examiner_name:
            manual = normalize_case_metadata(replace(manual, examiner=examiner_name))

        merged = analyze_case_metadata_from_documents(
            manual=manual,
            uploaded_files=uploaded_files,
        )
        save_bootstrap_metadata(report, merged, state=STATE_ANALYZED)

        warnings: list[str] = []
        try:
            document_excerpts = extract_text_from_uploads(uploaded_files)
        except Exception:
            document_excerpts = ""
        if not document_excerpts:
            warnings.append(
                "Não foi possível extrair texto dos documentos enviados. "
                "O laudo será montado com os dados disponíveis."
            )
        elif not is_ai_configured():
            warnings.append(
                "Serviço de IA indisponível. O laudo será montado com os dados disponíveis."
            )

        report.refresh_from_db()
        return JsonResponse(
            {
                "state": STATE_ANALYZED,
                "metadata": case_metadata_to_form_dict(merged),
                "pending_prompts": compute_pending_prompts(merged),
                "warnings": warnings,
            }
        )

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapBuildView(ForensicReportAuthorMixin, View):
    """Monta corpo do laudo a partir dos metadados analisados."""

    def post(self, request, pk):
        """Persiste blocos padronizados e marca bootstrap como concluído."""
        report = self.get_report()
        if bootstrap_state(report) == STATE_READY:
            return JsonResponse(bootstrap_status_payload(report))

        metadata = metadata_from_bootstrap(report.page_layout)
        try:
            build_forensic_report_from_bootstrap(
                report,
                examiner=self.examiner_profile,
                metadata=metadata,
            )
        except ValidationError as exc:
            return _validation_error_response(exc)

        report.refresh_from_db()
        return JsonResponse(bootstrap_status_payload(report))

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapStatusView(ForensicReportAuthorMixin, View):
    """Consulta estado atual do bootstrap interativo."""

    def get(self, request, pk):
        """Retorna metadados, prompts pendentes e mapa de nós."""
        report = self.get_report()
        return JsonResponse(bootstrap_status_payload(report))

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["GET"])


class ForensicBootstrapPromptView(ForensicReportAuthorMixin, View):
    """Registra resposta ou skip de prompt inline no editor."""

    def post(self, request, pk):
        """Atualiza metadados, sincroniza blocos e avança fila de prompts."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state not in (STATE_PROMPTING, STATE_ANALYZED):
            return JsonResponse(
                {"errors": ["Não há prompts pendentes para este laudo."]},
                status=400,
            )

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        field_name = str(payload.get("field", "")).strip()
        action = str(payload.get("action", "")).strip().lower()
        allowed_fields = {name for name, _label in CRITICAL_PROMPT_FIELDS}
        if field_name not in allowed_fields:
            return JsonResponse({"errors": ["Campo de prompt inválido."]}, status=400)
        if action not in {"submit", "skip"}:
            return JsonResponse({"errors": ["Informe action como submit ou skip."]}, status=400)

        bootstrap = bootstrap_status_payload(report)
        pending = bootstrap.get("pending_prompts", [])
        if pending and pending[0] != field_name:
            return JsonResponse({"errors": ["Prompt fora da ordem esperada."]}, status=400)

        try:
            if action == "skip":
                mark_prompt_skipped(report, field_name)
            else:
                raw_value = payload.get("value", "")
                validate_prompt_submit_value(field_name, str(raw_value))
                metadata = metadata_from_bootstrap(report.page_layout)
                updated = apply_prompt_field_value(metadata, field_name, str(raw_value))
                sync_forensic_metadata_fields(
                    report,
                    examiner=self.examiner_profile,
                    metadata=updated,
                    changed_fields={field_name},
                )
                save_bootstrap_after_metadata_update(report, updated)
        except ValidationError as exc:
            return _validation_error_response(exc)

        report.refresh_from_db()
        response = bootstrap_status_payload(report)
        response["reload"] = response.get("state") == STATE_READY
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapFinalizeView(ForensicReportAuthorMixin, View):
    """Persiste respostas e skips acumulados no frontend em uma única operação."""

    def post(self, request, pk):
        """Aplica lote de prompts e conclui bootstrap interativo."""
        report = self.get_report()
        if bootstrap_state(report) != STATE_PROMPTING:
            return JsonResponse(
                {"errors": ["Não há prompts pendentes para este laudo."]},
                status=400,
            )

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        raw_answers = payload.get("answers", {})
        raw_skipped = payload.get("skipped", [])
        if not isinstance(raw_answers, dict):
            return JsonResponse({"errors": ["Informe answers como objeto."]}, status=400)
        if not isinstance(raw_skipped, list):
            return JsonResponse({"errors": ["Informe skipped como lista."]}, status=400)

        try:
            finalize_bootstrap_prompts(
                report,
                examiner=self.examiner_profile,
                answers=raw_answers,
                skipped=[str(item) for item in raw_skipped],
            )
        except ValidationError as exc:
            return _validation_error_response(exc)

        report.refresh_from_db()
        response = bootstrap_status_payload(report)
        response["reload"] = True
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
