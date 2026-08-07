# reportline/reports/services/report_table_cell_content.py
"""
Normalização de conteúdo de células de tabela.

Suporta texto (legado como string) e imagens embutidas no corpo da tabela.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from reports.services.report_block_alignment import (
    default_text_align_for_table_cell,
    default_text_align_for_table_header,
    normalize_text_align,
)
from reports.services.report_inline_text import sanitize_inline_text_html


def normalize_table_header_cell(cell: Any) -> dict[str, Any]:
    """Normaliza cabeçalho de tabela com texto e alinhamento opcional."""
    if isinstance(cell, str):
        return {
            "text": sanitize_inline_text_html(cell),
            "align": default_text_align_for_table_header(),
        }

    if isinstance(cell, dict):
        if cell.get("type") == "image":
            raise ValidationError("Cabeçalho de tabela aceita apenas texto.")
        text = cell.get("text", "")
        if not isinstance(text, str):
            raise ValidationError("Cabeçalho de tabela exige campo text como string.")
        align = normalize_text_align(
            cell.get("align"),
            default=default_text_align_for_table_header(),
        )
        return {"text": sanitize_inline_text_html(text), "align": align}

    raise ValidationError("Cabeçalho de tabela aceita apenas texto.")


def normalize_table_body_cell(cell: Any) -> dict[str, Any]:
    """
    Normaliza célula do corpo da tabela.

    Aceita string legada (texto) ou objeto ``text`` / ``image``.
    """
    if isinstance(cell, str):
        return {
            "type": "text",
            "text": sanitize_inline_text_html(cell),
            "align": default_text_align_for_table_cell("text"),
        }

    if not isinstance(cell, dict):
        raise ValidationError("Célula de tabela deve ser texto ou objeto.")

    cell_type = cell.get("type", "text")
    if cell_type == "text":
        text = cell.get("text", "")
        if not isinstance(text, str):
            raise ValidationError("Célula de texto exige campo text como string.")
        align = normalize_text_align(
            cell.get("align"),
            default=default_text_align_for_table_cell("text"),
        )
        return {"type": "text", "text": sanitize_inline_text_html(text), "align": align}

    if cell_type == "image":
        alt = cell.get("alt", "")
        file_ref = cell.get("file", "")
        image_id = cell.get("image_id", "")
        width = cell.get("width", 0)
        height = cell.get("height", 0)
        if not isinstance(alt, str) or not isinstance(file_ref, str):
            raise ValidationError("Imagem na célula exige alt e file como texto.")
        if image_id is not None and not isinstance(image_id, (str, int)):
            raise ValidationError("Imagem na célula exige image_id como texto.")
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValidationError("Imagem na célula exige width e height inteiros.")
        align = normalize_text_align(
            cell.get("align"),
            default=default_text_align_for_table_cell("image"),
        )
        return {
            "type": "image",
            "alt": alt,
            "file": file_ref,
            "image_id": str(image_id) if image_id else "",
            "width": max(0, width),
            "height": max(0, height),
            "align": align,
        }

    raise ValidationError("Tipo de célula de tabela não suportado.")


def enrich_table_header_cell(cell: Any) -> dict[str, Any]:
    """Converte cabeçalho legado em objeto enriquecido para templates."""
    if isinstance(cell, str):
        return {
            "text": cell,
            "align": default_text_align_for_table_header(),
        }
    if isinstance(cell, dict):
        return {
            "text": str(cell.get("text", "")),
            "align": cell.get("align", default_text_align_for_table_header()),
        }
    return {"text": "", "align": default_text_align_for_table_header()}


def enrich_table_body_cell(cell: Any) -> Any:
    """Acrescenta URL de mídia em células de imagem para templates."""
    if isinstance(cell, str):
        return {
            "type": "text",
            "text": cell,
            "align": default_text_align_for_table_cell("text"),
        }

    if not isinstance(cell, dict):
        return cell

    if cell.get("type") != "image":
        enriched = dict(cell)
        enriched.setdefault("align", default_text_align_for_table_cell("text"))
        return enriched

    enriched = dict(cell)
    file_ref = enriched.get("file")
    if file_ref:
        from django.core.files.storage import default_storage

        enriched["url"] = default_storage.url(file_ref)
    enriched.setdefault("align", default_text_align_for_table_cell("image"))
    return enriched


def collect_image_ids_from_table_content(content: dict[str, Any] | None) -> list[str]:
    """Lista identificadores de imagens embutidas no corpo da tabela."""
    if not content:
        return []

    image_ids: list[str] = []
    for row in content.get("rows", []):
        if not isinstance(row, list):
            continue
        for cell in row:
            if isinstance(cell, dict) and cell.get("type") == "image":
                image_id = cell.get("image_id")
                if image_id:
                    image_ids.append(str(image_id))
    return image_ids
