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
    analyze_case_metadata_with_coverage,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.mixins import ForensicExaminerSPRequiredMixin
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    ALL_PROMPT_FIELD_NAMES,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    CRITICAL_PROMPT_FIELDS,
    STATE_ANALYZED,
    STATE_BUILDING,
    STATE_COLLECTING_PROMPTS,
    STATE_PROMPTING,
    STATE_READY,
    STATE_SHELL_CREATED,
    bootstrap_state,
    bootstrap_status_payload,
    compute_pending_prompts,
    forensic_bootstrap_prompt_config,
    get_bootstrap_meta,
    mark_prompt_skipped,
    metadata_from_bootstrap,
    save_bootstrap_after_analyze,
    save_bootstrap_after_metadata_update,
    save_bootstrap_metadata,
    set_bootstrap_state,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_finalize import (
    finalize_bootstrap_prompts,
)
from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
    BUILD_STEP_IDS,
    BUILD_STEP_LABELS,
    advance_forensic_body_build_step,
    count_completed_interactive_steps,
    count_interactive_build_steps,
    is_interactive_build_step,
)
from institution_ic_sp.forensic_report.services.forensic_report_metadata_sync import (
    apply_prompt_field_value,
    sync_forensic_metadata_fields,
    validate_prompt_submit_value,
)
from institution_ic_sp.forensic_report.workflows.generic.services.report_draft_builder import (
    build_forensic_report_from_bootstrap,
)
from reports.services.report_editor_context import (
    render_editable_block_html,
    render_outline_refresh_payload,
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
        if state in (STATE_BUILDING, STATE_PROMPTING, STATE_COLLECTING_PROMPTS):
            return JsonResponse(
                {"errors": ["A análise não está disponível nesta etapa do laudo."]},
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

        merged, field_coverage = analyze_case_metadata_with_coverage(
            manual=manual,
            uploaded_files=uploaded_files,
        )
        save_bootstrap_after_analyze(report, merged, field_coverage=field_coverage)

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
        current_state = bootstrap_state(report)
        response: dict[str, object] = {
            "state": current_state,
            "metadata": case_metadata_to_form_dict(merged),
            "pending_prompts": compute_pending_prompts(
                merged,
                field_coverage=field_coverage,
            ),
            "warnings": warnings,
        }
        if current_state == STATE_COLLECTING_PROMPTS:
            response["prompt_config"] = forensic_bootstrap_prompt_config(report)
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapBuildView(ForensicReportAuthorMixin, View):
    """Monta corpo do laudo a partir dos metadados analisados."""

    def post(self, request, pk):
        """Persiste blocos padronizados e marca bootstrap como concluído."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state == STATE_READY:
            return JsonResponse(bootstrap_status_payload(report))
        if state == STATE_BUILDING:
            return JsonResponse(bootstrap_status_payload(report))
        if state != STATE_ANALYZED:
            message = (
                "Responda aos dados pendentes antes de montar o laudo."
                if state == STATE_COLLECTING_PROMPTS
                else "Analise os documentos antes de montar o laudo."
            )
            return JsonResponse({"errors": [message]}, status=400)

        set_bootstrap_state(report, STATE_BUILDING)
        metadata = metadata_from_bootstrap(report.page_layout)
        try:
            build_forensic_report_from_bootstrap(
                report,
                examiner=self.examiner_profile,
                metadata=metadata,
            )
        except ValidationError as exc:
            set_bootstrap_state(report, STATE_ANALYZED)
            return _validation_error_response(exc)
        except Exception:
            set_bootstrap_state(report, STATE_ANALYZED)
            raise

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


class ForensicBootstrapBuildStepView(ForensicReportAuthorMixin, View):
    """Avança um passo na montagem incremental do corpo do laudo."""

    def post(self, request, pk):
        """Cria próximo bloco, retorna HTML parcial e atualiza sumário."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state not in (STATE_ANALYZED, STATE_BUILDING):
            return JsonResponse(
                {"errors": ["A montagem incremental não está disponível nesta etapa."]},
                status=400,
            )

        try:
            created_nodes, done, final_state, step_id = advance_forensic_body_build_step(
                report,
                examiner=self.examiner_profile,
            )
        except ValidationError as exc:
            return _validation_error_response(exc)
        except ValueError as exc:
            return JsonResponse({"errors": [str(exc)]}, status=400)

        report.refresh_from_db()
        metadata = metadata_from_bootstrap(report.page_layout)
        outline_payload = render_outline_refresh_payload(report, request)
        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        progress = bootstrap.get("build_progress") if isinstance(bootstrap.get("build_progress"), dict) else {}
        step_index = progress.get("step_index", len(BUILD_STEP_IDS) if done else 0)

        interactive_total = count_interactive_build_steps(metadata)
        interactive_index = count_completed_interactive_steps(metadata, step_index)

        response = {
            "state": final_state,
            "done": done,
            "step_id": step_id,
            "step_label": BUILD_STEP_LABELS.get(step_id or "", "Montando laudo…"),
            "step_index": interactive_index,
            "total_steps": interactive_total,
            "animated": is_interactive_build_step(step_id),
            "blocks_html": [
                render_editable_block_html(node, request) for node in created_nodes
            ],
            "outline_html": outline_payload["html"],
            "heading_numbers": outline_payload["heading_numbers"],
            "report_title": report.title,
            "header_report_number_text": metadata.header_report_number_text,
        }
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapPromptView(ForensicReportAuthorMixin, View):
    """Registra resposta ou skip de prompt inline no editor."""

    def post(self, request, pk):
        """Atualiza metadados, sincroniza blocos e avança fila de prompts."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state not in (STATE_PROMPTING, STATE_COLLECTING_PROMPTS, STATE_ANALYZED):
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
        allowed_fields = ALL_PROMPT_FIELD_NAMES
        if field_name not in allowed_fields:
            return JsonResponse({"errors": ["Campo de prompt inválido."]}, status=400)
        if action not in {"submit", "skip"}:
            return JsonResponse({"errors": ["Informe action como submit ou skip."]}, status=400)

        bootstrap = bootstrap_status_payload(report)
        pending = bootstrap.get("pending_prompts", [])
        if pending and pending[0] != field_name:
            return JsonResponse({"errors": ["Prompt fora da ordem esperada."]}, status=400)

        try:
            pre_build = state == STATE_COLLECTING_PROMPTS
            if action == "skip":
                mark_prompt_skipped(report, field_name)
            else:
                raw_value = payload.get("value", "")
                validate_prompt_submit_value(field_name, str(raw_value))
                metadata = metadata_from_bootstrap(report.page_layout)
                updated = apply_prompt_field_value(metadata, field_name, str(raw_value))
                if not pre_build:
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
        state = bootstrap_state(report)
        if state not in (STATE_COLLECTING_PROMPTS, STATE_PROMPTING):
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
        response["reload"] = bootstrap_state(report) == STATE_READY
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
