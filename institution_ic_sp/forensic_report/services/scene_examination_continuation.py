"""
Persistência da continuação de exame de local no bootstrap pericial.
"""

from __future__ import annotations

from dataclasses import replace

from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_PROPERTY_SCENE,
    normalize_exam_category,
)
from institution_ic_sp.forensic_report.common.services.scene_location import (
    SceneLocationData,
    normalize_scene_location,
    resolve_scene_location,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    empty_bootstrap_payload,
    get_bootstrap_meta,
    is_initial_build_completed,
    metadata_from_bootstrap,
    resolve_bootstrap_state,
    skipped_prompts_from_bootstrap,
)
from reports.models import Report


def is_scene_continuation_completed(page_layout: dict | None) -> bool:
    """Indica se a etapa de continuação de exame de local já foi concluída."""
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
    location_raw = raw.get("location", {})
    location = normalize_scene_location(location_raw if isinstance(location_raw, dict) else {})
    return {
        "prompt": str(prompt).strip(),
        "image_ids": [str(item) for item in image_ids],
        "location": {
            "kind": location.kind,
            "address": location.address,
            "latitude": location.latitude,
            "longitude": location.longitude,
        }
        if location.is_present
        else {},
    }


def save_scene_examination_continuation(
    report: Report,
    *,
    exam_category: str,
    prompt: str = "",
    image_ids: list[str] | None = None,
    location: SceneLocationData | None = None,
) -> Report:
    """
    Persiste categoria de exame e características do local no bootstrap.

    Após a montagem inicial, inicia fase de inserção da seção de local quando
    aplicável ou conclui o bootstrap para módulos diferidos.
    """
    if not is_initial_build_completed(report.page_layout):
        raise ValueError("A montagem inicial do laudo deve ser concluída antes da continuação.")

    normalized_category = normalize_exam_category(exam_category)
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    metadata = metadata_from_bootstrap(report.page_layout)
    metadata = replace(metadata, exam_category=normalized_category)
    resolved_location = resolve_scene_location(manual=location or SceneLocationData(), report=report)

    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["exam_category"] = normalized_category
    bootstrap["scene_continuation_completed"] = True

    if normalized_category == EXAM_CATEGORY_PROPERTY_SCENE:
        scene_payload: dict[str, object] = {
            "prompt": prompt.strip(),
            "image_ids": list(image_ids or []),
        }
        if resolved_location.is_present:
            scene_payload["location"] = {
                "kind": resolved_location.kind,
                "address": resolved_location.address,
                "latitude": resolved_location.latitude,
                "longitude": resolved_location.longitude,
            }
        bootstrap["scene_characteristics"] = scene_payload
    else:
        bootstrap.pop("scene_characteristics", None)
        bootstrap.pop("scene_examination_content", None)

    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)

    if normalized_category == EXAM_CATEGORY_PROPERTY_SCENE:
        from institution_ic_sp.forensic_report.services.scene_examination_content import (
            attach_scene_examination_content,
            generate_scene_examination_content,
        )

        content = generate_scene_examination_content(report)
        attach_scene_examination_content(report, content)
        from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
            start_scene_build_phase,
        )

        start_scene_build_phase(report)
    else:
        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        skipped = skipped_prompts_from_bootstrap(report.page_layout)
        bootstrap["state"] = resolve_bootstrap_state(metadata, skipped=skipped)
        report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)

    report.save(update_fields=["page_layout", "updated_at"])
    return report
