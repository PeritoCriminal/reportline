# reportline/institution_ic_sp/forensic_report/views/forensic_bootstrap_api_views.py
"""
API JSON do bootstrap interativo de laudos periciais no editor.
"""

from __future__ import annotations

import json
from dataclasses import replace

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.views import View

from common.privacy.exceptions import ExternalAiBlockedError
from institution_ic_sp.forensic_report.common.ai.client import is_ai_configured
from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads
from institution_ic_sp.forensic_report.common.services.case_metadata import normalize_case_metadata
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    analyze_case_metadata_with_coverage,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.common.services.exam_category import (
    DEFERRED_MODULE_TODO_MESSAGES,
    EXAM_CATEGORY_PROPERTY_SCENE,
    VALID_EXAM_CATEGORIES,
    is_deferred_module_category,
    normalize_exam_category,
)
from institution_ic_sp.forensic_report.common.services.scene_location import (
    exam_location_from_dossier,
    normalize_scene_location,
    resolve_scene_location,
    scene_location_to_payload,
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
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_PROMPTING,
    STATE_READY,
    STATE_SHELL_CREATED,
    bootstrap_state,
    bootstrap_status_payload,
    compute_pending_prompts,
    forensic_bootstrap_prompt_config,
    forensic_scene_continuation_runner_config,
    get_bootstrap_meta,
    is_initial_build_completed,
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
    BUILD_PHASE_INITIAL,
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
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    save_scene_examination_continuation,
)
from institution_ic_sp.forensic_report.workflows.initial_data.services.report_draft_builder import (
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
        if state in (STATE_BUILDING, STATE_PROMPTING, STATE_COLLECTING_PROMPTS, STATE_COLLECTING_SCENE_CONTINUATION):
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

        try:
            merged, field_coverage, extensions = analyze_case_metadata_with_coverage(
                manual=manual,
                uploaded_files=uploaded_files,
                audit_context={
                    "operation": "metadata_extraction",
                    "user_id": str(request.user.pk),
                    "report_id": str(report.pk),
                },
            )
        except ExternalAiBlockedError as exc:
            return JsonResponse({"errors": [str(exc)]}, status=422)

        save_bootstrap_after_analyze(
            report,
            merged,
            field_coverage=field_coverage,
            document_count=len(uploaded_files),
            extensions=extensions,
        )

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
                "Serviço de análise indisponível. O laudo será montado com os dados disponíveis."
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
            "inferred_exam_category": normalize_exam_category(merged.exam_category),
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
        if state not in (STATE_ANALYZED, STATE_BUILDING):
            message = "Complete a continuação do exame antes de montar o laudo."
            if state == STATE_COLLECTING_SCENE_CONTINUATION:
                message = "Informe o tipo de exame antes de montar o laudo."
            elif state == STATE_COLLECTING_PROMPTS:
                message = "Responda aos dados pendentes antes de montar o laudo."
            elif state == STATE_SHELL_CREATED:
                message = "Analise os documentos antes de montar o laudo."
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
            message = "Responda aos dados pendentes antes de montar o laudo."
            if state == STATE_COLLECTING_SCENE_CONTINUATION:
                message = "Informe o tipo de exame antes de montar a seção de local."
            elif state == STATE_COLLECTING_PROMPTS:
                message = "Responda aos dados pendentes antes de montar o laudo."
            elif state == STATE_SHELL_CREATED:
                message = "Analise os documentos antes de montar o laudo."
            return JsonResponse({"errors": [message]}, status=400)

        try:
            created_nodes, done, final_state, step_id, build_phase = advance_forensic_body_build_step(
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
        build_phase = str(progress.get("phase") or BUILD_PHASE_INITIAL)

        interactive_total = count_interactive_build_steps(
            metadata,
            page_layout=report.page_layout,
            phase=build_phase,
        )
        interactive_index = count_completed_interactive_steps(
            metadata,
            step_index,
            page_layout=report.page_layout,
            phase=build_phase,
        )

        response = {
            "state": final_state,
            "done": done,
            "step_id": step_id,
            "step_label": BUILD_STEP_LABELS.get(step_id or "", "Montando laudo…"),
            "step_index": interactive_index,
            "total_steps": interactive_total,
            "animated": is_interactive_build_step(step_id),
            "build_phase": build_phase,
            "blocks_html": [
                render_editable_block_html(node, request) for node in created_nodes
            ],
            "outline_html": outline_payload["html"],
            "heading_numbers": outline_payload["heading_numbers"],
            "report_title": report.title,
            "header_report_number_text": metadata.header_report_number_text,
        }
        if final_state == STATE_COLLECTING_SCENE_CONTINUATION:
            response["scene_continuation_config"] = forensic_scene_continuation_runner_config(report)
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


class ForensicBootstrapAttendanceContextView(ForensicReportAuthorMixin, View):
    """Persiste respostas dos prompts de contexto de atendimento no exame de local."""

    def post(self, request, pk):
        """Aplica lote de respostas sobre circunstâncias do atendimento pericial."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state != STATE_COLLECTING_SCENE_CONTINUATION:
            return JsonResponse(
                {"errors": ["Os prompts de contexto de atendimento não estão disponíveis nesta etapa."]},
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

        from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
            _forensic_attendance_context_prompt_config,
        )
        from institution_ic_sp.forensic_report.services.scene_attendance_context_finalize import (
            finalize_attendance_context_prompts,
        )

        try:
            finalize_attendance_context_prompts(
                report,
                answers=raw_answers,
                skipped=[str(item) for item in raw_skipped],
            )
        except ValidationError as exc:
            return _validation_error_response(exc)

        report.refresh_from_db()
        response = _forensic_attendance_context_prompt_config(report)
        response["state"] = bootstrap_state(report)
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])


class ForensicBootstrapSceneContinuationView(ForensicReportAuthorMixin, View):
    """Registra tipo de exame e características do local no bootstrap."""

    def post(self, request, pk):
        """Persiste continuação de exame de local e avança o bootstrap."""
        report = self.get_report()
        state = bootstrap_state(report)
        if state != STATE_COLLECTING_SCENE_CONTINUATION:
            return JsonResponse(
                {"errors": ["A continuação de exame de local não está disponível nesta etapa."]},
                status=400,
            )
        if not is_initial_build_completed(report.page_layout):
            return JsonResponse(
                {"errors": ["Conclua a montagem inicial do laudo antes de informar o tipo de exame."]},
                status=400,
            )

        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"errors": ["JSON inválido."]}, status=400)

        raw_category = str(payload.get("exam_category", "")).strip().lower()
        if raw_category not in VALID_EXAM_CATEGORIES:
            return JsonResponse({"errors": ["Categoria de exame inválida."]}, status=400)
        exam_category = raw_category

        prompt = str(payload.get("prompt", "")).strip()
        raw_images = payload.get("images")
        raw_image_ids = payload.get("image_ids", [])
        if raw_image_ids is not None and not isinstance(raw_image_ids, list):
            return JsonResponse({"errors": ["Informe image_ids como lista."]}, status=400)
        if raw_images is not None and not isinstance(raw_images, list):
            return JsonResponse({"errors": ["Informe images como lista."]}, status=400)

        from reports.services.report_image_attachments import normalize_report_image_attachments

        legacy_image_ids = [str(item) for item in (raw_image_ids or []) if str(item).strip()]
        attachments = normalize_report_image_attachments(raw_images, legacy_image_ids=legacy_image_ids)
        image_ids = [item.image_id for item in attachments]

        raw_location = payload.get("location", {})
        location = normalize_scene_location(raw_location if isinstance(raw_location, dict) else {})
        resolved_location = resolve_scene_location(manual=location, report=report)

        has_scene_input = bool(prompt or image_ids or resolved_location.is_present)
        if exam_category == EXAM_CATEGORY_PROPERTY_SCENE and not has_scene_input:
            return JsonResponse(
                {"errors": ["Informe localização, imagens ou orientações sobre o local."]},
                status=400,
            )

        if image_ids and not self.examiner_profile.can_send_images_to_external_ai:
            return JsonResponse(
                {
                    "errors": [
                        "Seu perfil não está autorizado a enviar imagens a serviços "
                        "externos de IA. Use orientações em texto ou solicite habilitação "
                        "ao administrador."
                    ]
                },
                status=403,
            )

        try:
            save_scene_examination_continuation(
                report,
                exam_category=exam_category,
                prompt=prompt,
                images=attachments,
                location=resolved_location,
                allow_external_images=self.examiner_profile.can_send_images_to_external_ai,
                audit_context={
                    "operation": "scene_examination",
                    "user_id": str(request.user.pk),
                    "report_id": str(report.pk),
                },
            )
        except ExternalAiBlockedError as exc:
            return JsonResponse({"errors": [str(exc)]}, status=422)

        report.refresh_from_db()
        current_state = bootstrap_state(report)
        response: dict[str, object] = {
            "state": current_state,
            "exam_category": exam_category,
            "metadata": case_metadata_to_form_dict(metadata_from_bootstrap(report.page_layout)),
        }
        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        build_progress = bootstrap.get("build_progress")
        if isinstance(build_progress, dict):
            response["build_phase"] = build_progress.get("phase")
        if is_deferred_module_category(exam_category):
            response["todo_message"] = DEFERRED_MODULE_TODO_MESSAGES[exam_category]
        return JsonResponse(response)

    def http_method_not_allowed(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(["POST"])
