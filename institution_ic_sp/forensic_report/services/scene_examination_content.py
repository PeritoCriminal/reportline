# reportline/institution_ic_sp/forensic_report/services/scene_examination_content.py
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
    scene_location_for_report,
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
from reports.services.report_caption_text import normalize_caption_text
from reports.services.report_image_attachments import normalize_report_image_attachments


def scene_examination_content_from_bootstrap(page_layout: dict | None) -> dict[str, str | list]:
    """Retorna parágrafos e imagens inferidos da seção de exame de local."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("scene_examination_content", {})
    if not isinstance(raw, dict):
        return {"report_images": []}
    report_images = raw.get("report_images", [])
    if not isinstance(report_images, list):
        report_images = []
    normalized_images: list[dict[str, str]] = []
    for item in report_images:
        if not isinstance(item, dict):
            continue
        image_id = str(item.get("image_id", "")).strip()
        caption = normalize_caption_text(str(item.get("caption", "")).strip())
        if image_id:
            normalized_images.append({"image_id": image_id, "caption": caption})
    return {
        "characteristics_heading": str(raw.get("characteristics_heading", "")).strip(),
        "attendance_context_paragraph": str(
            raw.get("attendance_context_paragraph", "")
        ).strip(),
        "characteristics_paragraph": str(raw.get("characteristics_paragraph", "")).strip(),
        "report_images": normalized_images,
    }


def should_build_scene_examination_section(
    metadata: CaseMetadata,
    page_layout: dict | None,
) -> bool:
    """Indica se a seção de exame de local deve entrar na montagem incremental."""
    if not is_property_scene_category(metadata.exam_category):
        return False
    return is_scene_continuation_completed(page_layout)


def generate_scene_examination_content(
    report: Report,
    *,
    allow_external_images: bool = False,
    audit_context: dict | None = None,
) -> dict[str, str | list]:
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
    location = scene_location_for_report(report)
    attachments = normalize_report_image_attachments(
        characteristics.get("images"),
        legacy_image_ids=list(characteristics.get("image_ids", [])),
    )
    return infer_scene_examination_content(
        report=report,
        metadata=metadata,
        scene_prompt=str(characteristics.get("prompt", "")),
        scene_image_attachments=attachments,
        location=location,
        allow_external_images=allow_external_images,
        audit_context=audit_context,
    )


def attach_scene_examination_content(report: Report, content: dict[str, str]) -> Report:
    """Anexa conteúdo inferido ao bootstrap do laudo."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    bootstrap["scene_examination_content"] = content
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    return report


def generate_and_save_scene_examination_content(report: Report) -> dict[str, str | list]:
    """Infere e persiste parágrafos de exame de local no bootstrap do laudo."""
    content = generate_scene_examination_content(report)
    attach_scene_examination_content(report, content)
    report.save(update_fields=["page_layout", "updated_at"])
    return content
