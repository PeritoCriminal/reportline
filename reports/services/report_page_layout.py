"""
Layout de página do relatório (cabeçalho repetido no PDF).

Define modelos tabulares de cabeçalho, normalização do JSON e enriquecimento
de células de logo para renderização no editor.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError

from reports.services.report_inline_text import (
    sanitize_header_text_html,
    sanitize_inline_text_html,
)
from reports.services.report_image_processing import CM_PER_INCH, DISPLAY_DPI
from reports.services.report_table_column_widths import normalize_column_widths

HEADER_LOGO_INITIAL_HEIGHT_CM = 3
HEADER_LOGO_INITIAL_HEIGHT_PX = round(
    HEADER_LOGO_INITIAL_HEIGHT_CM * DISPLAY_DPI / CM_PER_INCH
)

HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT = "logo_left_text_right"
HEADER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT = "text_left_logo_right"
HEADER_TEMPLATE_LOGO_TEXT_LOGO = "logo_text_logo"

HEADER_TEMPLATE_IDS = frozenset(
    {
        HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
        HEADER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT,
        HEADER_TEMPLATE_LOGO_TEXT_LOGO,
    }
)

HEADER_TEMPLATE_LABELS = {
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT: "Logo à esquerda, texto à direita",
    HEADER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT: "Texto à esquerda, logo à direita",
    HEADER_TEMPLATE_LOGO_TEXT_LOGO: "Logo, texto e logo",
}

HEADER_TEMPLATE_SPECS: dict[str, dict[str, Any]] = {
    HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT: {
        "column_widths": [1, 99],
        "cells": [
            {"type": "logo", "logo_slot": "primary"},
            {"type": "text", "align": "left"},
        ],
    },
    HEADER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT: {
        "column_widths": [99, 1],
        "cells": [
            {"type": "text", "align": "left"},
            {"type": "logo", "logo_slot": "primary"},
        ],
    },
    HEADER_TEMPLATE_LOGO_TEXT_LOGO: {
        "column_widths": [1, 98, 1],
        "cells": [
            {"type": "logo", "logo_slot": "primary"},
            {"type": "text", "align": "center"},
            {"type": "logo", "logo_slot": "secondary"},
        ],
    },
}


def default_page_layout() -> dict[str, Any]:
    """Retorna layout de página vazio (sem cabeçalho ativo)."""
    return {
        "header": {
            "enabled": False,
            "template_id": None,
            "column_widths": [],
            "cells": [],
        }
    }


def default_logo_cell(*, logo_slot: str = "primary") -> dict[str, Any]:
    """Monta célula vazia de logo para o cabeçalho."""
    return {
        "type": "logo",
        "logo_slot": logo_slot,
        "file": "",
        "image_id": "",
        "width": 0,
        "height": 0,
        "alt": "",
    }


def default_text_cell(*, align: str = "left") -> dict[str, Any]:
    """Monta célula vazia de texto para o cabeçalho."""
    return {
        "type": "text",
        "text": "",
        "align": align,
    }


def initial_header_logo_display_size(
    natural_width: int,
    natural_height: int,
) -> tuple[int, int]:
    """
    Calcula dimensões iniciais de exibição da logo do cabeçalho.

    Usa altura fixa equivalente a 3 cm (96 DPI); a largura preserva a proporção.
    """
    target_height = max(1, HEADER_LOGO_INITIAL_HEIGHT_PX)
    if natural_width <= 0 or natural_height <= 0:
        return target_height, target_height

    aspect_ratio = natural_width / natural_height
    display_height = target_height
    display_width = max(1, round(display_height * aspect_ratio))
    return display_width, display_height


def _default_cell_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    cell_type = spec.get("type")
    if cell_type == "logo":
        return default_logo_cell(logo_slot=str(spec.get("logo_slot", "primary")))
    if cell_type == "text":
        return default_text_cell(align=str(spec.get("align", "left")))
    raise ValidationError("Tipo de célula de cabeçalho inválido.")


def build_header_cells_for_template(
    template_id: str,
    *,
    existing_cells: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Monta células do cabeçalho para o modelo informado, preservando conteúdo compatível."""
    if template_id not in HEADER_TEMPLATE_IDS:
        raise ValidationError("Modelo de cabeçalho inválido.")

    spec = HEADER_TEMPLATE_SPECS[template_id]
    previous = existing_cells or []
    cells: list[dict[str, Any]] = []

    for index, slot in enumerate(spec["cells"]):
        cell = _default_cell_from_spec(slot)
        if index < len(previous) and previous[index].get("type") == cell["type"]:
            if cell["type"] == "logo":
                for key in ("file", "image_id", "width", "height", "alt", "logo_slot"):
                    if previous[index].get(key) not in (None, ""):
                        cell[key] = previous[index][key]
            else:
                cell["text"] = sanitize_header_text_html(str(previous[index].get("text", "")))
                cell["align"] = str(previous[index].get("align", cell["align"]))
        cells.append(normalize_header_cell(cell))

    return cells


def normalize_logo_cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza célula de logo do cabeçalho."""
    logo_slot = str(cell.get("logo_slot", "primary"))
    if logo_slot not in ("primary", "secondary"):
        raise ValidationError("Slot de logo inválido no cabeçalho.")

    file_ref = cell.get("file", "")
    image_id = cell.get("image_id", "")
    width = cell.get("width", 0)
    height = cell.get("height", 0)
    alt = cell.get("alt", "")

    if not isinstance(file_ref, str) or not isinstance(alt, str):
        raise ValidationError("Logo do cabeçalho exige file e alt como texto.")
    if image_id is not None and not isinstance(image_id, (str, int)):
        raise ValidationError("Logo do cabeçalho exige image_id como texto.")
    if not isinstance(width, int) or not isinstance(height, int):
        raise ValidationError("Logo do cabeçalho exige width e height inteiros.")

    return {
        "type": "logo",
        "logo_slot": logo_slot,
        "file": file_ref,
        "image_id": str(image_id) if image_id else "",
        "width": max(0, width),
        "height": max(0, height),
        "alt": alt,
    }


def normalize_text_cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza célula de texto do cabeçalho."""
    text = cell.get("text", "")
    align = cell.get("align", "left")
    if not isinstance(text, str):
        raise ValidationError("Célula de texto do cabeçalho exige campo text.")
    if align not in ("left", "center", "right"):
        raise ValidationError("Alinhamento de célula de cabeçalho inválido.")
    return {
        "type": "text",
        "text": sanitize_header_text_html(text),
        "align": align,
    }


def normalize_header_cell(cell: Any) -> dict[str, Any]:
    """Normaliza uma célula do cabeçalho."""
    if not isinstance(cell, dict):
        raise ValidationError("Cada célula do cabeçalho deve ser um objeto.")
    cell_type = cell.get("type")
    if cell_type == "logo":
        return normalize_logo_cell(cell)
    if cell_type == "text":
        return normalize_text_cell(cell)
    raise ValidationError("Tipo de célula de cabeçalho inválido.")


def normalize_header_layout(header: Any) -> dict[str, Any]:
    """Normaliza payload do cabeçalho de página."""
    if not isinstance(header, dict):
        raise ValidationError("Cabeçalho deve ser um objeto JSON.")

    enabled = bool(header.get("enabled", False))
    template_id = header.get("template_id")
    cells_payload = header.get("cells", [])
    column_widths_payload = header.get("column_widths", [])

    if not enabled:
        return {
            "enabled": False,
            "template_id": None,
            "column_widths": [],
            "cells": [],
        }

    if template_id not in HEADER_TEMPLATE_IDS:
        raise ValidationError("Informe um modelo de cabeçalho válido.")

    if not isinstance(cells_payload, list):
        raise ValidationError("Células do cabeçalho devem ser uma lista.")

    spec = HEADER_TEMPLATE_SPECS[template_id]
    expected_len = len(spec["cells"])
    if len(cells_payload) != expected_len:
        cells_payload = build_header_cells_for_template(template_id)

    cells = [normalize_header_cell(cell) for cell in cells_payload]
    column_widths = normalize_column_widths(
        column_widths_payload or spec["column_widths"],
        expected_len,
    )

    return {
        "enabled": True,
        "template_id": template_id,
        "column_widths": column_widths,
        "cells": cells,
    }


def normalize_page_layout(payload: Any) -> dict[str, Any]:
    """Normaliza layout completo de página do relatório."""
    if payload in (None, ""):
        return default_page_layout()
    if not isinstance(payload, dict):
        raise ValidationError("Layout de página deve ser um objeto JSON.")

    header = normalize_header_layout(payload.get("header", {}))
    return {"header": header}


def apply_header_template(
    page_layout: dict[str, Any] | None,
    template_id: str,
) -> dict[str, Any]:
    """Ativa cabeçalho com o modelo informado."""
    if template_id not in HEADER_TEMPLATE_IDS:
        raise ValidationError("Modelo de cabeçalho inválido.")

    current = normalize_page_layout(page_layout)
    existing_cells = current["header"].get("cells", [])
    spec = HEADER_TEMPLATE_SPECS[template_id]

    current["header"] = {
        "enabled": True,
        "template_id": template_id,
        "column_widths": list(spec["column_widths"]),
        "cells": build_header_cells_for_template(
            template_id,
            existing_cells=existing_cells,
        ),
    }
    return current


def enrich_header_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Acrescenta URL pública às células de logo para templates."""
    from django.core.files.storage import default_storage

    enriched: list[dict[str, Any]] = []
    for cell in cells:
        item = dict(cell)
        if item.get("type") == "logo" and item.get("file"):
            item["url"] = default_storage.url(item["file"])
        enriched.append(item)
    return enriched


def enrich_page_layout_for_editor(page_layout: dict[str, Any] | None) -> dict[str, Any]:
    """Prepara layout de página para renderização no editor."""
    normalized = normalize_page_layout(page_layout)
    header = normalized["header"]
    if header.get("enabled"):
        header = dict(header)
        header["cells"] = enrich_header_cells(header.get("cells", []))
        header["template_label"] = HEADER_TEMPLATE_LABELS.get(
            header.get("template_id"),
            "",
        )
        normalized = dict(normalized)
        normalized["header"] = header
    return normalized


def update_logo_cell_from_image(
    page_layout: dict[str, Any],
    *,
    cell_index: int,
    image_payload: dict[str, Any],
) -> dict[str, Any]:
    """Atualiza célula de logo após upload de imagem."""
    normalized = normalize_page_layout(page_layout)
    header = normalized["header"]
    if not header.get("enabled"):
        raise ValidationError("Cabeçalho não está ativo.")

    cells = [dict(cell) for cell in header["cells"]]
    if cell_index < 0 or cell_index >= len(cells):
        raise ValidationError("Índice de célula de logo inválido.")
    if cells[cell_index].get("type") != "logo":
        raise ValidationError("A célula informada não é de logo.")

    logo_slot = cells[cell_index].get("logo_slot", "primary")
    natural_width = int(image_payload.get("width", 0) or 0)
    natural_height = int(image_payload.get("height", 0) or 0)
    display_width, display_height = initial_header_logo_display_size(
        natural_width,
        natural_height,
    )
    cells[cell_index] = normalize_logo_cell(
        {
            "type": "logo",
            "logo_slot": logo_slot,
            "file": image_payload.get("file", ""),
            "image_id": image_payload.get("image_id", ""),
            "width": display_width,
            "height": display_height,
            "alt": image_payload.get("alt", ""),
        }
    )
    header = dict(header)
    header["cells"] = cells
    normalized = dict(normalized)
    normalized["header"] = header
    return normalized
