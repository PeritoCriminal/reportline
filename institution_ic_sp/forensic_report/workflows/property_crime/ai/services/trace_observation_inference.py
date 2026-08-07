# reportline/institution_ic_sp/forensic_report/workflows/property_crime/ai/services/trace_observation_inference.py
"""
Inferência de texto para vestígios (Elementos Observados) em exame de local patrimonial.
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
from institution_ic_sp.forensic_report.registry import PROPERTY_CRIME_WORKFLOW
from reports.models import Report, ReportImage
from reports.services.report_caption_text import normalize_caption_text
from reports.services.report_image_attachments import ReportImageAttachment

logger = logging.getLogger(__name__)


def _default_trace_observation_content() -> dict[str, str | list]:
    """Retorna conteúdo vazio quando a IA não estiver disponível."""
    return {
        "trace_paragraph": "",
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


def _trace_images_json_for_prompt(attachments: list[ReportImageAttachment]) -> str:
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
    """Valida legendas inferidas para imagens marcadas para exibição no laudo."""
    show_attachments = [item for item in attachments if item.show_in_report]
    if not show_attachments:
        return []

    captions_by_id: dict[str, str] = {}
    if payload and isinstance(payload.get("report_images"), list):
        for item in payload["report_images"]:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id", "")).strip()
            caption = normalize_caption_text(str(item.get("caption", "")).strip())
            if image_id:
                captions_by_id[image_id] = caption

    report_images: list[dict[str, str]] = []
    for attachment in show_attachments:
        caption = captions_by_id.get(attachment.image_id, "").strip()
        if not caption:
            caption = attachment.proposed_caption.strip()
        caption = normalize_caption_text(caption)
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
        return _default_trace_observation_content()

    paragraph = str(payload.get("trace_paragraph", "")).strip()
    return {
        "trace_paragraph": paragraph,
        "report_images": _normalize_report_images(payload, attachments),
    }


def infer_trace_observation_content(
    *,
    report: Report,
    metadata: CaseMetadata,
    trace_prompt: str = "",
    trace_image_attachments: list[ReportImageAttachment] | None = None,
    allow_external_images: bool = False,
    audit_context: dict | None = None,
) -> dict[str, str | list]:
    """
    Infere parágrafo e legendas para um vestígio observado no exame de local.

    Usa orientações do perito, imagens (quando permitido) e biblioteca traces.md.
    """
    attachments = list(trace_image_attachments or [])

    system_template = load_prompt_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        task="trace_observation",
        name="system",
    )
    traces_style = load_writing_style_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        name="traces",
    )
    system_prompt = render_prompt_template(
        system_template,
        traces_style=traces_style,
    )
    user_template = load_prompt_markdown(
        workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
        task="trace_observation",
        name="user",
    )
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
        trace_prompt=trace_prompt.strip() or "(nenhuma)",
        trace_images_json=_trace_images_json_for_prompt(attachments),
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
