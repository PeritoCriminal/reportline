"""
Inferência de texto para a seção Descrição e Exame do Local.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path

from django.conf import settings

from institution_ic_sp.forensic_report.common.ai.client import is_ai_configured
from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_prompt_markdown,
    render_prompt_template,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from reports.models import Report, ReportImage

logger = logging.getLogger(__name__)

ALLOWED_CHARACTERISTICS_HEADINGS = frozenset(
    {
        "Características do Local",
        "Características da Propriedade",
        "Características do Imóvel",
    }
)


def _default_scene_examination_content() -> dict[str, str]:
    """Retorna conteúdo vazio quando a IA não estiver disponível."""
    return {
        "characteristics_heading": "Características do Local",
        "attendance_context_paragraph": "",
        "characteristics_paragraph": "",
    }


def _image_data_urls(report: Report, image_ids: list[str]) -> list[str]:
    """Converte imagens do laudo em data URLs para chamada multimodal."""
    urls: list[str] = []
    if not image_ids:
        return urls
    images = ReportImage.objects.filter(report=report, pk__in=image_ids)
    for report_image in images:
        if not report_image.image:
            continue
        path = Path(report_image.image.path)
        if not path.is_file():
            continue
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        urls.append(f"data:{mime_type};base64,{encoded}")
    return urls


def _complete_json_with_images(
    *,
    system: str,
    user_text: str,
    image_data_urls: list[str],
) -> dict | None:
    """Solicita JSON ao modelo com texto e imagens opcionais."""
    if not is_ai_configured():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.exception("Pacote openai não instalado.")
        return None

    model = getattr(settings, "FORENSIC_AI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_content: list[dict] = [{"type": "text", "text": user_text}]
    for data_url in image_data_urls:
        user_content.append({"type": "image_url", "image_url": {"url": data_url}})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception:
        logger.exception("Falha na inferência de exame de local.")
        return None

    content = response.choices[0].message.content
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Resposta da IA de exame de local não é JSON válido.")
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_ai_content(payload: dict | None) -> dict[str, str]:
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
    }


def infer_scene_examination_content(
    *,
    report: Report,
    metadata: CaseMetadata,
    scene_prompt: str = "",
    scene_image_ids: list[str] | None = None,
    location: SceneLocationData | None = None,
    document_excerpts: str = "",
) -> dict[str, str]:
    """
    Infere parágrafos de contexto de atendimento e características do local.

    Usa metadados administrativos, orientações do perito, localização e imagens.
    """
    system_prompt = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="scene_examination",
        name="system",
    )
    user_template = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="scene_examination",
        name="user",
    )

    location_text = ""
    if location and location.is_present:
        location_text = location.display_text

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
        document_excerpts=document_excerpts.strip() or "(nenhum)",
    )

    image_urls = _image_data_urls(report, list(scene_image_ids or []))
    payload = _complete_json_with_images(
        system=system_prompt,
        user_text=user_prompt,
        image_data_urls=image_urls,
    )
    return _normalize_ai_content(payload)
