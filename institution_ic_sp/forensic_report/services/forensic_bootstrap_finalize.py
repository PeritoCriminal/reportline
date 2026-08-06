"""
Finalização em lote dos prompts inline do bootstrap pericial.

Aplica respostas e skips acumulados no frontend com uma única persistência.
Antes da montagem do corpo, apenas metadados são atualizados; após a montagem,
sincroniza blocos já existentes (fluxo legado).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    ALL_PROMPT_FIELD_NAMES,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_ANALYZED,
    STATE_COLLECTING_PROMPTS,
    STATE_PROMPTING,
    attach_bootstrap_meta,
    bootstrap_state,
    compute_pending_prompts,
    field_coverage_from_bootstrap,
    get_bootstrap_meta,
    metadata_from_bootstrap,
    resolve_bootstrap_state,
    skipped_prompts_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.forensic_report_metadata_sync import (
    apply_prompt_field_value,
    sync_forensic_metadata_fields,
    validate_prompt_submit_value,
)
from profiles.models import ForensicExaminerSP
from reports.models import Report

_ALLOWED_FIELDS = ALL_PROMPT_FIELD_NAMES


@transaction.atomic
def finalize_bootstrap_prompts(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    answers: dict[str, str],
    skipped: list[str],
) -> Report:
    """
    Aplica respostas e skips em lote.

    No estado ``collecting_prompts`` (pré-montagem), persiste metadados e
    libera a montagem incremental. No estado ``prompting`` (pós-montagem),
    também sincroniza blocos existentes.
    """
    state = bootstrap_state(report)
    if state not in (STATE_COLLECTING_PROMPTS, STATE_PROMPTING):
        raise ValidationError("Não há prompts pendentes para este laudo.")

    pre_build = state == STATE_COLLECTING_PROMPTS
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    pending_raw = bootstrap.get("pending_prompts", [])
    pending = [str(item) for item in pending_raw] if isinstance(pending_raw, list) else []
    if not pending:
        raise ValidationError("Não há prompts pendentes para este laudo.")

    answers_clean = {
        str(field): str(value)
        for field, value in answers.items()
        if str(field) in _ALLOWED_FIELDS
    }
    skipped_set = skipped_prompts_from_bootstrap(report.page_layout) | {
        str(field) for field in skipped if str(field) in _ALLOWED_FIELDS
    }

    if answers_clean.keys() & skipped_set:
        raise ValidationError("Um campo não pode ser informado e pulado ao mesmo tempo.")

    for field in pending:
        if field not in answers_clean and field not in skipped_set:
            raise ValidationError("Informe ou pule todos os campos pendentes antes de concluir.")

    metadata = metadata_from_bootstrap(report.page_layout)
    changed_fields: set[str] = set()

    for field_name in pending:
        if field_name in skipped_set:
            continue
        raw_value = answers_clean[field_name]
        validate_prompt_submit_value(field_name, raw_value)
        metadata = apply_prompt_field_value(metadata, field_name, raw_value)
        changed_fields.add(field_name)

    skipped_set.update(str(field) for field in skipped if str(field) in _ALLOWED_FIELDS)

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    manual_fields = {
        str(item)
        for item in bootstrap.get("manual_prompt_fields", [])
        if str(item) in _ALLOWED_FIELDS
    }
    for field_name in pending:
        if field_name in skipped_set:
            continue
        if field_name in answers_clean:
            manual_fields.add(field_name)

    if changed_fields and not pre_build:
        sync_forensic_metadata_fields(
            report,
            examiner=examiner,
            metadata=metadata,
            changed_fields=changed_fields,
        )
        report.refresh_from_db()

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    coverage = field_coverage_from_bootstrap(report.page_layout)
    bootstrap["skipped_prompts"] = sorted(skipped_set)
    bootstrap["manual_prompt_fields"] = sorted(manual_fields)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["pending_prompts"] = compute_pending_prompts(
        metadata,
        skipped=skipped_set,
        field_coverage=coverage,
    )
    if pre_build:
        bootstrap["state"] = STATE_ANALYZED
    else:
        bootstrap["state"] = resolve_bootstrap_state(metadata, skipped=skipped_set)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
