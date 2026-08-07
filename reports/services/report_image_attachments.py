# reportline/reports/services/report_image_attachments.py
"""
Normalização de anexos de imagem com opções de exibição e legenda proposta.

Padrão de projeto para uploads de imagem com miniatura, checkbox de exibição
no laudo e campo de legenda sugerida pelo perito.
"""

from __future__ import annotations

from dataclasses import dataclass

from reports.services.report_caption_text import normalize_caption_text


@dataclass(frozen=True)
class ReportImageAttachment:
    """Metadados de uma imagem enviada ao laudo."""

    image_id: str
    show_in_report: bool = True
    proposed_caption: str = ""


def normalize_report_image_attachments(
    raw_images: object,
    *,
    legacy_image_ids: list[str] | None = None,
) -> list[ReportImageAttachment]:
    """
    Normaliza payload de imagens da API ou lista legada de IDs.

    Aceita ``images`` como lista de objetos ``{ image_id, show_in_report, proposed_caption }``.
    Quando apenas ``image_ids`` é informado, assume exibição no laudo sem legenda proposta.
    """
    attachments: list[ReportImageAttachment] = []
    seen_ids: set[str] = set()

    if isinstance(raw_images, list):
        for item in raw_images:
            if not isinstance(item, dict):
                continue
            image_id = str(item.get("image_id", "")).strip()
            if not image_id or image_id in seen_ids:
                continue
            show_in_report = bool(item.get("show_in_report", True))
            proposed_caption = normalize_caption_text(str(item.get("proposed_caption", "")).strip())
            attachments.append(
                ReportImageAttachment(
                    image_id=image_id,
                    show_in_report=show_in_report,
                    proposed_caption=proposed_caption,
                )
            )
            seen_ids.add(image_id)

    if attachments:
        return attachments

    for image_id in legacy_image_ids or []:
        cleaned = str(image_id).strip()
        if not cleaned or cleaned in seen_ids:
            continue
        attachments.append(ReportImageAttachment(image_id=cleaned))
        seen_ids.add(cleaned)
    return attachments


def report_image_attachment_ids(attachments: list[ReportImageAttachment]) -> list[str]:
    """Retorna IDs na ordem de upload."""
    return [item.image_id for item in attachments]


def report_image_attachments_to_payload(
    attachments: list[ReportImageAttachment],
) -> list[dict[str, object]]:
    """Serializa anexos para persistência no bootstrap."""
    return [
        {
            "image_id": item.image_id,
            "show_in_report": item.show_in_report,
            "proposed_caption": item.proposed_caption,
        }
        for item in attachments
    ]
