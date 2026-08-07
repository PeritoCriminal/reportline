# reportline/institution_ic_sp/forensic_report/workflows/property_crime/ai/services/scene_examination_inference.py
"""
Inferência de texto para a seção Descrição e Exame do Local (crime patrimonial).
"""

from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path

from institution_ic_sp.forensic_report.common.ai.gateway import complete_json_with_images_safe
from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_prompt_markdown,
    load_writing_style_markdown,
    render_prompt_template,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
    attendance_context_summary_for_prompt,
    scene_attendance_context_from_bootstrap,
)
from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData
from institution_ic_sp.forensic_report.registry import PROPERTY_CRIME_WORKFLOW
from reports.models import Report, ReportImage
from reports.services.report_image_attachments import ReportImageAttachment

logger = logging.getLogger(__name__)

ALLOWED_CHARACTERISTICS_HEADINGS = frozenset(
    {
        "Características do Local",
        "Características da Propriedade",
        "Características do Imóvel",
    }
)


def _default_scene_examination_content() -> dict[str, str | list]:
    """Retorna conteúdo vazio quando a IA não estiver disponível."""
    return {
        "characteristics_heading": "Características do Local",
        "attendance_context_paragraph": "",
        "characteristics_paragraph": "",
        "report_images": [],
    }


def _image_data_urls(report: Report, image_ids: list[str]) -> list[str]:
    """Converte imagens do laudo em data URLs para chamada multimodal."""
    urls: list[str] = []
    if not image_ids:
        return urls
    images = ReportImage.objects.filter(report=report, pk__in=image_ids)
    images_by_id = {str(item.pk): item for item in images}
    for image_id in image_ids:
        report_image = images_by_id.get(image_id)
        if not report_image or not report_image.image:
            continue
        path = Path(report_image.image.path)
        if not path.is_file():
            continue
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = path.read_bytes()
        import base64

        data = base64.b64encode(encoded).decode("ascii")
        urls.append(f"data:{mime_type};base64,{data}")
    return urls


def _scene_images_json_for_prompt(attachments: list[ReportImageAttachment]) -> str:
    """Serializa metadados das imagens para o prompt do usuário."""
    if not attachments:
        return "(nenhuma)"
    payload = [
        {
            "image_id": item.image_id,
            "show_in_report": item.show_in_report,
            "proposed_caption": item.proposed_caption or "(nenhuma)",
        }
        for item in attachments
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalize_report_images(
    payload: dict | None,
    attachments: list[ReportImageAttachment],
) -> list[dict[str, str]]:
    """
    Valida legendas inferidas apenas para imagens marcadas para exibição no laudo.

    Preserva a ordem de upload e usa a legenda proposta como fallback.
    """
    show_attachments = [item for item in attachments if item.show_in_report]
    if not show_attachments:
        return []

    captions_by_id: dict[str, str] = {}
    if payload and isinstance(payload.get("report_images"), list):
        for item in payload["report_images"]:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id", "")).strip()
            caption = str(item.get("caption", "")).strip()
            if image_id:
                captions_by_id[image_id] = caption

    report_images: list[dict[str, str]] = []
    for attachment in show_attachments:
        caption = captions_by_id.get(attachment.image_id, "").strip()
        if not caption:
            caption = attachment.proposed_caption.strip()
        report_images.append(
            {
                "image_id": attachment.image_id,
                "caption": caption,
            }
        )
    return report_images


def _normalize_ai_content(
    payload: dict | None,
    *,
    attachments: list[ReportImageAttachment],
) -> dict[str, str | list]:
    """Valida e normaliza JSON inferido para persistência no bootstrap."""
    if not payload:
        return _default_scene_examination_content()

    heading = str(payload.get("characteristics_heading", "")).strip()
    if heading not in ALLOWED_CHARACTERISTICS_HEADINGS:
        heading = "Características do Local"

    attendance = str(payload.get("attendance_context_paragraph", "")).strip()
    characteristics = str(payload.get("characteristics_paragraph", "")).strip()
    return {
        "characteristics_heading": heading,
        "attendance_context_paragraph": attendance,
        "characteristics_paragraph": characteristics,
        "report_images": _normalize_report_images(payload, attachments),
    }


def infer_scene_examination_content(
    *,
    report: Report,
    metadata: CaseMetadata,
    scene_prompt: str = "",
    scene_image_ids: list[str] | None = None,
    scene_image_attachments: list[ReportImageAttachment] | None = None,
    location: SceneLocationData | None = None,
    document_excerpts: str = "",
    allow_external_images: bool = False,
    audit_context: dict | None = None,
) -> dict[str, str | list]:
    """
    Infere parágrafos de contexto de atendimento, características do local e legendas.

    Usa metadados administrativos, orientações do perito, localização e imagens
    (quando o perito tiver permissão institucional).
    """
    attachments = list(scene_image_attachments or [])
    if not attachments and scene_image_ids:
        attachments = [
            ReportImageAttachment(image_id=str(image_id))
            for image_id in scene_image_ids
            if str(image_id).strip()
        ]

    system_template = load_prompt_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        task="scene_examination",
        name="system",
    )
    attendance_context_style = load_writing_style_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        name="attendance_context",
    )
    characteristics_style = load_writing_style_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        name="characteristics",
    )
    system_prompt = render_prompt_template(
        system_template,
        attendance_context_style=attendance_context_style,
        characteristics_style=characteristics_style,
    )
    user_template = load_prompt_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        task="scene_examination",
        name="user",
    )

    location_text = ""
    if location and location.is_present:
        location_text = location.display_text

    attendance_context = scene_attendance_context_from_bootstrap(report.page_layout)

    user_prompt = render_prompt_template(
        user_template,
        metadata_json=json.dumps(
            {
                "exam_objective": metadata.exam_objective,
                "requesting_authority": metadata.requesting_authority,
                "police_district": metadata.police_district,
                "occurrence_report": metadata.occurrence_report,
                "examination_at": metadata.examination_at.isoformat()
                if metadata.examination_at
                else "",
                "examiner": metadata.examiner,
            },
            ensure_ascii=False,
            indent=2,
        ),
        scene_prompt=scene_prompt.strip() or "(nenhuma)",
        location_text=location_text or "(não informada)",
        attendance_context_text=attendance_context_summary_for_prompt(attendance_context),
        document_excerpts=document_excerpts.strip() or "(nenhum)",
        scene_images_json=_scene_images_json_for_prompt(attachments),
    )

    image_ids = [item.image_id for item in attachments]
    image_urls = _image_data_urls(report, image_ids)
    payload = complete_json_with_images_safe(
        system=system_prompt,
        user_text=user_prompt,
        image_data_urls=image_urls,
        allow_external_images=allow_external_images,
        audit_context=audit_context,
    )
    return _normalize_ai_content(payload, attachments=attachments)
