"""
Finalização em lote dos prompts inline do bootstrap pericial.

Aplica respostas e skips acumulados no frontend com uma única persistência
e sincronização de blocos no servidor.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    CRITICAL_PROMPT_FIELDS,
    STATE_PROMPTING,
    attach_bootstrap_meta,
    bootstrap_state,
    compute_pending_prompts,
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

_ALLOWED_FIELDS = {name for name, _label in CRITICAL_PROMPT_FIELDS}


@transaction.atomic
def finalize_bootstrap_prompts(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    answers: dict[str, str],
    skipped: list[str],
) -> Report:
    """
    Aplica respostas e skips em lote e conclui o bootstrap interativo.

    Exige cobertura completa da fila ``pending_prompts`` persistida no laudo.
    """
    if bootstrap_state(report) != STATE_PROMPTING:
        raise ValidationError("Não há prompts pendentes para este laudo.")

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

    if changed_fields:
        sync_forensic_metadata_fields(
            report,
            examiner=examiner,
            metadata=metadata,
            changed_fields=changed_fields,
        )
        report.refresh_from_db()

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    bootstrap["skipped_prompts"] = sorted(skipped_set)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["pending_prompts"] = compute_pending_prompts(metadata, skipped=skipped_set)
    bootstrap["state"] = resolve_bootstrap_state(metadata, skipped=skipped_set)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
