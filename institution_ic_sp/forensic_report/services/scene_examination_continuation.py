"""
Persistência da continuação de exame de local no bootstrap pericial.
"""

from __future__ import annotations

from dataclasses import replace

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_PROPERTY_SCENE,
    normalize_exam_category,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_ANALYZED,
    STATE_COLLECTING_PROMPTS,
    attach_bootstrap_meta,
    compute_pending_prompts,
    empty_bootstrap_payload,
    field_coverage_from_bootstrap,
    get_bootstrap_meta,
    metadata_from_bootstrap,
    skipped_prompts_from_bootstrap,
)
from reports.models import Report


def is_scene_continuation_completed(page_layout: dict | None) -> bool:
    """Indica se a etapa de continuação de exame de local já foi concluída."""
    from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
        get_bootstrap_meta,
    )

    bootstrap = get_bootstrap_meta(page_layout) or {}
    return bool(bootstrap.get("scene_continuation_completed"))


def scene_characteristics_from_bootstrap(page_layout: dict | None) -> dict[str, object]:
    """Retorna prompt e IDs de imagens coletados na continuação de local."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("scene_characteristics", {})
    if not isinstance(raw, dict):
        return {"prompt": "", "image_ids": []}
    image_ids = raw.get("image_ids", [])
    if not isinstance(image_ids, list):
        image_ids = []
    prompt = raw.get("prompt", "")
    return {
        "prompt": str(prompt).strip(),
        "image_ids": [str(item) for item in image_ids],
    }


def resolve_state_after_scene_continuation(report: Report, metadata: CaseMetadata) -> str:
    """Define próximo estado do bootstrap após concluir a continuação de local."""
    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    coverage = field_coverage_from_bootstrap(report.page_layout)
    pending = compute_pending_prompts(metadata, skipped=skipped, field_coverage=coverage)
    return STATE_COLLECTING_PROMPTS if pending else STATE_ANALYZED


def save_scene_examination_continuation(
    report: Report,
    *,
    exam_category: str,
    prompt: str = "",
    image_ids: list[str] | None = None,
) -> Report:
    """
    Persiste categoria de exame e características do local no bootstrap.

    Marca a continuação como concluída e avança para prompts administrativos
    ou montagem incremental conforme metadados pendentes.
    """
    normalized_category = normalize_exam_category(exam_category)
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    metadata = metadata_from_bootstrap(report.page_layout)
    metadata = replace(metadata, exam_category=normalized_category)

    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["exam_category"] = normalized_category
    bootstrap["scene_continuation_completed"] = True

    if normalized_category == EXAM_CATEGORY_PROPERTY_SCENE:
        bootstrap["scene_characteristics"] = {
            "prompt": prompt.strip(),
            "image_ids": list(image_ids or []),
        }
    else:
        bootstrap.pop("scene_characteristics", None)

    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    coverage = field_coverage_from_bootstrap(report.page_layout)
    bootstrap["pending_prompts"] = compute_pending_prompts(
        metadata,
        skipped=skipped,
        field_coverage=coverage,
    )
    bootstrap["state"] = resolve_state_after_scene_continuation(report, metadata)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
