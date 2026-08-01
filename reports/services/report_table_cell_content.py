"""
Normalização de conteúdo de células de tabela.

Suporta texto (legado como string) e imagens embutidas no corpo da tabela.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError


def normalize_table_header_cell(cell: Any) -> str:
    """Normaliza cabeçalho de tabela — apenas texto."""
    if isinstance(cell, str):
        return cell
    if isinstance(cell, dict) and cell.get("type", "text") == "text":
        return str(cell.get("text", ""))
    raise ValidationError("Cabeçalho de tabela aceita apenas texto.")


def normalize_table_body_cell(cell: Any) -> dict[str, Any]:
    """
    Normaliza célula do corpo da tabela.

    Aceita string legada (texto) ou objeto ``text`` / ``image``.
    """
    if isinstance(cell, str):
        return {"type": "text", "text": cell}

    if not isinstance(cell, dict):
        raise ValidationError("Célula de tabela deve ser texto ou objeto.")

    cell_type = cell.get("type", "text")
    if cell_type == "text":
        text = cell.get("text", "")
        if not isinstance(text, str):
            raise ValidationError("Célula de texto exige campo text como string.")
        return {"type": "text", "text": text}

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
        return {
            "type": "image",
            "alt": alt,
            "file": file_ref,
            "image_id": str(image_id) if image_id else "",
            "width": max(0, width),
            "height": max(0, height),
        }

    raise ValidationError("Tipo de célula de tabela não suportado.")


def enrich_table_body_cell(cell: Any) -> Any:
    """Acrescenta URL de mídia em células de imagem para templates."""
    if isinstance(cell, str):
        return cell

    if not isinstance(cell, dict) or cell.get("type") != "image":
        return cell

    enriched = dict(cell)
    file_ref = enriched.get("file")
    if file_ref:
        from django.core.files.storage import default_storage

        enriched["url"] = default_storage.url(file_ref)
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
