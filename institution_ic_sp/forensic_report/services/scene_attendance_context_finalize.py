"""
Finalização em lote dos prompts de contexto de atendimento no exame de local.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
    normalize_scene_attendance_context,
    scene_attendance_context_from_bootstrap,
    scene_attendance_context_to_payload,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_COLLECTING_SCENE_CONTINUATION,
    attach_bootstrap_meta,
    bootstrap_state,
    get_bootstrap_meta,
)
from institution_ic_sp.forensic_report.services.scene_attendance_context_prompts import (
    ATTENDANCE_CONTEXT_FIELD_NAMES,
    apply_attendance_context_answers,
    compute_pending_attendance_context_prompts,
)
from reports.models import Report


def skipped_attendance_context_prompts_from_bootstrap(page_layout: dict | None) -> set[str]:
    """Retorna campos de contexto de atendimento marcados como pulados."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("skipped_attendance_context_prompts", [])
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item) in ATTENDANCE_CONTEXT_FIELD_NAMES}


@transaction.atomic
def finalize_attendance_context_prompts(
    report: Report,
    *,
    answers: dict[str, str],
    skipped: list[str],
) -> Report:
    """Persiste respostas e skips dos prompts de contexto de atendimento."""
    state = bootstrap_state(report)
    if state != STATE_COLLECTING_SCENE_CONTINUATION:
        raise ValidationError("Os prompts de contexto de atendimento não estão disponíveis nesta etapa.")

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    context = scene_attendance_context_from_bootstrap(report.page_layout)
    pending = compute_pending_attendance_context_prompts(
        context,
        skipped=skipped_attendance_context_prompts_from_bootstrap(report.page_layout),
    )
    if not pending:
        raise ValidationError("Não há prompts de contexto de atendimento pendentes.")

    answers_clean = {
        str(field): str(value).strip()
        for field, value in answers.items()
        if str(field) in ATTENDANCE_CONTEXT_FIELD_NAMES
    }
    skipped_set = skipped_attendance_context_prompts_from_bootstrap(report.page_layout) | {
        str(field) for field in skipped if str(field) in ATTENDANCE_CONTEXT_FIELD_NAMES
    }

    if answers_clean.keys() & skipped_set:
        raise ValidationError("Um campo não pode ser informado e pulado ao mesmo tempo.")

    for field in pending:
        if field not in answers_clean and field not in skipped_set:
            raise ValidationError("Informe ou pule todos os campos pendentes antes de concluir.")

    for field_name, raw_value in answers_clean.items():
        if field_name in skipped_set:
            continue
        if not raw_value:
            raise ValidationError(f"Informe um valor para {field_name}.")

    context = apply_attendance_context_answers(context, answers_clean)
    context = normalize_scene_attendance_context(scene_attendance_context_to_payload(context))
    skipped_set.update(str(field) for field in skipped if str(field) in ATTENDANCE_CONTEXT_FIELD_NAMES)

    bootstrap["scene_attendance_context"] = scene_attendance_context_to_payload(context)
    bootstrap["skipped_attendance_context_prompts"] = sorted(skipped_set)
    bootstrap["pending_attendance_context_prompts"] = compute_pending_attendance_context_prompts(
        context,
        skipped=skipped_set,
    )
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
