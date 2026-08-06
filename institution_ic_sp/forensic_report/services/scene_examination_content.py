"""
Persistência e geração do conteúdo de exame de local no bootstrap.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import (
    is_property_scene_category,
)
from institution_ic_sp.forensic_report.common.services.scene_location import (
    SceneLocationData,
    scene_location_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    get_bootstrap_meta,
    metadata_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    is_scene_continuation_completed,
)
from institution_ic_sp.forensic_report.workflows.property_crime.ai.services.scene_examination_inference import (
    infer_scene_examination_content,
)
from reports.models import Report


def scene_examination_content_from_bootstrap(page_layout: dict | None) -> dict[str, str]:
    """Retorna parágrafos inferidos da seção de exame de local."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("scene_examination_content", {})
    if not isinstance(raw, dict):
        return {}
    return {
        "characteristics_heading": str(raw.get("characteristics_heading", "")).strip(),
        "attendance_context_paragraph": str(
            raw.get("attendance_context_paragraph", "")
        ).strip(),
        "characteristics_paragraph": str(raw.get("characteristics_paragraph", "")).strip(),
    }


def should_build_scene_examination_section(
    metadata: CaseMetadata,
    page_layout: dict | None,
) -> bool:
    """Indica se a seção de exame de local deve entrar na montagem incremental."""
    if not is_property_scene_category(metadata.exam_category):
        return False
    return is_scene_continuation_completed(page_layout)


def generate_scene_examination_content(report: Report) -> dict[str, str]:
    """
    Infere parágrafos de exame de local a partir do bootstrap atual.

    Não persiste — use ``attach_scene_examination_content`` para gravar.
    """
    metadata = metadata_from_bootstrap(report.page_layout)
    if not is_property_scene_category(metadata.exam_category):
        return {}

    from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
        scene_characteristics_from_bootstrap,
    )

    characteristics = scene_characteristics_from_bootstrap(report.page_layout)
    location = scene_location_from_bootstrap(report.page_layout)
    return infer_scene_examination_content(
        report=report,
        metadata=metadata,
        scene_prompt=str(characteristics.get("prompt", "")),
        scene_image_ids=list(characteristics.get("image_ids", [])),
        location=location,
    )


def attach_scene_examination_content(report: Report, content: dict[str, str]) -> Report:
    """Anexa conteúdo inferido ao bootstrap do laudo."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    bootstrap["scene_examination_content"] = content
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    return report


def generate_and_save_scene_examination_content(report: Report) -> dict[str, str]:
    """Infere e persiste parágrafos de exame de local no bootstrap do laudo."""
    content = generate_scene_examination_content(report)
    attach_scene_examination_content(report, content)
    report.save(update_fields=["page_layout", "updated_at"])
    return content
