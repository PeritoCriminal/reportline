"""
Layout de página do relatório (cabeçalho e rodapé repetidos no PDF).

Define modelos tabulares, normalização do JSON e enriquecimento de células
de logo para renderização no editor.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError

from reports.services.report_block_indent import normalize_indent_level
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
HEADER_LOGO_INITIAL_WIDTH_CM = 1.5
HEADER_LOGO_INITIAL_WIDTH_PX = round(
    HEADER_LOGO_INITIAL_WIDTH_CM * DISPLAY_DPI / CM_PER_INCH
)
PAGE_BAND_LOGO_INITIAL_HEIGHT_PX = HEADER_LOGO_INITIAL_HEIGHT_PX

LAYOUT_TEMPLATE_TEXT_ONLY = "text_only"
LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT = "logo_left_text_right"
LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT = "text_left_logo_right"
LAYOUT_TEMPLATE_LOGO_TEXT_LOGO = "logo_text_logo"

HEADER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT = LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT
HEADER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT = LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT
HEADER_TEMPLATE_LOGO_TEXT_LOGO = LAYOUT_TEMPLATE_LOGO_TEXT_LOGO

FOOTER_TEMPLATE_TEXT_ONLY = LAYOUT_TEMPLATE_TEXT_ONLY
FOOTER_TEMPLATE_LOGO_LEFT_TEXT_RIGHT = LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT
FOOTER_TEMPLATE_TEXT_LEFT_LOGO_RIGHT = LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT
FOOTER_TEMPLATE_LOGO_TEXT_LOGO = LAYOUT_TEMPLATE_LOGO_TEXT_LOGO

HEADER_TEMPLATE_IDS = frozenset(
    {
        LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
        LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT,
        LAYOUT_TEMPLATE_LOGO_TEXT_LOGO,
    }
)

FOOTER_TEMPLATE_IDS = frozenset(
    {
        LAYOUT_TEMPLATE_TEXT_ONLY,
        LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT,
        LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT,
        LAYOUT_TEMPLATE_LOGO_TEXT_LOGO,
    }
)

HEADER_EXTRA_ROW_TYPE_TEXT = "text"
HEADER_EXTRA_ROW_TYPE_RULE = "rule"

HEADER_EXTRA_ROW_TYPES = frozenset(
    {
        HEADER_EXTRA_ROW_TYPE_TEXT,
        HEADER_EXTRA_ROW_TYPE_RULE,
    }
)

MAX_HEADER_EXTRA_ROWS = 8

HEADER_TEMPLATE_LABELS = {
    LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT: "Logo à esquerda, texto à direita",
    LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT: "Texto à esquerda, logo à direita",
    LAYOUT_TEMPLATE_LOGO_TEXT_LOGO: "Logo, texto e logo",
}

FOOTER_TEMPLATE_LABELS = {
    LAYOUT_TEMPLATE_TEXT_ONLY: "Texto simples",
    LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT: "Imagem à esquerda, texto à direita",
    LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT: "Texto à esquerda, imagem à direita",
    LAYOUT_TEMPLATE_LOGO_TEXT_LOGO: "Imagem, texto e imagem",
}

_SHARED_LOGO_TEXT_SPECS: dict[str, dict[str, Any]] = {
    LAYOUT_TEMPLATE_LOGO_LEFT_TEXT_RIGHT: {
        "column_widths": [1, 99],
        "cells": [
            {"type": "logo", "logo_slot": "primary"},
            {"type": "text", "align": "left"},
        ],
    },
    LAYOUT_TEMPLATE_TEXT_LEFT_LOGO_RIGHT: {
        "column_widths": [99, 1],
        "cells": [
            {"type": "text", "align": "left"},
            {"type": "logo", "logo_slot": "primary"},
        ],
    },
    LAYOUT_TEMPLATE_LOGO_TEXT_LOGO: {
        "column_widths": [1, 98, 1],
        "cells": [
            {"type": "logo", "logo_slot": "primary"},
            {"type": "text", "align": "center"},
            {"type": "logo", "logo_slot": "secondary"},
        ],
    },
}

HEADER_TEMPLATE_SPECS: dict[str, dict[str, Any]] = {
    key: {
        "column_widths": list(spec["column_widths"]),
        "cells": [dict(cell) for cell in spec["cells"]],
    }
    for key, spec in _SHARED_LOGO_TEXT_SPECS.items()
}

FOOTER_TEMPLATE_SPECS: dict[str, dict[str, Any]] = {
    LAYOUT_TEMPLATE_TEXT_ONLY: {
        "column_widths": [100],
        "cells": [{"type": "text", "align": "center", "show_page_number": True}],
    },
    **{
        key: {
            "column_widths": list(spec["column_widths"]),
            "cells": [
                dict(cell, show_page_number=True) if cell["type"] == "text" else dict(cell)
                for cell in spec["cells"]
            ],
        }
        for key, spec in _SHARED_LOGO_TEXT_SPECS.items()
    },
}


def _disabled_band_layout() -> dict[str, Any]:
    """Retorna faixa de layout (cabeçalho/rodapé) desativada."""
    return {
        "enabled": False,
        "template_id": None,
        "column_widths": [],
        "cells": [],
        "extra_rows": [],
    }


def default_page_layout() -> dict[str, Any]:
    """Retorna layout de página vazio (sem cabeçalho nem rodapé ativos)."""
    return {
        "header": _disabled_band_layout(),
        "footer": _disabled_band_layout(),
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


def default_header_extra_rule_row() -> dict[str, Any]:
    """Monta linha horizontal de largura total abaixo do cabeçalho principal."""
    return {"type": HEADER_EXTRA_ROW_TYPE_RULE}


def default_header_extra_text_row(
    *,
    align: str = "left",
    muted: bool = False,
    indent_level: int = 0,
    first_line_indent: bool = False,
) -> dict[str, Any]:
    """Monta linha de texto de largura total abaixo do cabeçalho principal."""
    cell = default_text_cell(
        align=align,
        indent_level=indent_level,
        first_line_indent=first_line_indent,
    )
    cell["muted"] = muted
    return cell


def default_text_cell(
    *,
    align: str = "left",
    show_page_number: bool = False,
    indent_level: int = 0,
    first_line_indent: bool = False,
) -> dict[str, Any]:
    """Monta célula vazia de texto para cabeçalho ou rodapé."""
    cell = {
        "type": "text",
        "text": "",
        "align": align,
        "indent_level": indent_level,
        "first_line_indent": first_line_indent,
    }
    if show_page_number:
        cell["show_page_number"] = True
    return cell


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


def initial_header_logo_display_size_by_width(
    natural_width: int,
    natural_height: int,
) -> tuple[int, int]:
    """
    Calcula dimensões iniciais de exibição da logo do cabeçalho.

    Usa largura fixa equivalente a 1,5 cm (96 DPI); a altura preserva a proporção.
    """
    target_width = max(1, HEADER_LOGO_INITIAL_WIDTH_PX)
    if natural_width <= 0 or natural_height <= 0:
        return target_width, target_width

    aspect_ratio = natural_width / natural_height
    display_width = target_width
    display_height = max(1, round(display_width / aspect_ratio))
    return display_width, display_height


def clamp_header_logo_display_size_by_width(
    display_width: int,
    display_height: int,
) -> tuple[int, int]:
    """
    Limita dimensões de exibição da logo à largura institucional de 1,5 cm.

    Preserva a proporção quando a logo persistida exceder a largura alvo.
    """
    width = max(0, int(display_width or 0))
    height = max(0, int(display_height or 0))
    if width <= 0 or height <= 0:
        return width, height
    if width <= HEADER_LOGO_INITIAL_WIDTH_PX:
        return width, height

    scale = HEADER_LOGO_INITIAL_WIDTH_PX / width
    return (
        HEADER_LOGO_INITIAL_WIDTH_PX,
        max(1, round(height * scale)),
    )


def _format_css_cm(value_px: int) -> str:
    """Converte pixels de referência (96 DPI) em unidade CSS ``cm``."""
    value_cm = value_px * CM_PER_INCH / DISPLAY_DPI
    formatted = f"{value_cm:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}cm"


def logo_display_size_style(width_px: int, height_px: int) -> str:
    """
    Monta declarações CSS inline para logo com dimensões físicas corretas.

    Usa ``cm`` em vez de ``px`` para que preview e PDF respeitem a escala da
    folha A4 mesmo quando a viewport reduz a largura da página.
    """
    width = max(0, int(width_px or 0))
    height = max(0, int(height_px or 0))
    if width <= 0 or height <= 0:
        return ""
    return (
        f"width: {_format_css_cm(width)}; "
        f"height: {_format_css_cm(height)}; "
        "max-width: 100%; object-fit: contain;"
    )


def prepare_logo_cell_for_document(
    cell: dict[str, Any],
    page_layout: dict[str, Any] | None,
    *,
    band: str,
) -> dict[str, Any]:
    """
    Normaliza célula de logo para leitura/preview/PDF.

    Em laudos periciais, limita emblemas institucionais à largura de 1,5 cm
    e expõe ``display_size_style`` com unidades físicas.
    """
    from reports.services.report_kind import is_forensic_report_layout

    prepared = dict(cell)
    if prepared.get("type") != "logo":
        return prepared

    width = int(prepared.get("width", 0) or 0)
    height = int(prepared.get("height", 0) or 0)
    if band == "header" and is_forensic_report_layout(page_layout):
        width, height = clamp_header_logo_display_size_by_width(width, height)
        prepared["width"] = width
        prepared["height"] = height

    display_style = logo_display_size_style(width, height)
    if display_style:
        prepared["display_size_style"] = display_style
    return prepared


initial_footer_logo_display_size = initial_header_logo_display_size


def _default_cell_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    cell_type = spec.get("type")
    if cell_type == "logo":
        return default_logo_cell(logo_slot=str(spec.get("logo_slot", "primary")))
    if cell_type == "text":
        return default_text_cell(
            align=str(spec.get("align", "left")),
            show_page_number=bool(spec.get("show_page_number", False)),
        )
    raise ValidationError("Tipo de célula de layout inválido.")


def _build_band_cells_for_template(
    template_specs: dict[str, dict[str, Any]],
    template_id: str,
    *,
    existing_cells: list[dict[str, Any]] | None = None,
    text_normalizer=None,
) -> list[dict[str, Any]]:
    """Monta células para o modelo informado, preservando conteúdo compatível."""
    if template_id not in template_specs:
        raise ValidationError("Modelo de layout inválido.")

    if text_normalizer is None:
        text_normalizer = normalize_text_cell

    spec = template_specs[template_id]
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
                cell["indent_level"] = previous[index].get(
                    "indent_level",
                    cell.get("indent_level", 0),
                )
                cell["first_line_indent"] = bool(
                    previous[index].get(
                        "first_line_indent",
                        cell.get("first_line_indent", False),
                    )
                )
                if "show_page_number" in cell:
                    cell["show_page_number"] = bool(
                        previous[index].get("show_page_number", cell["show_page_number"])
                    )
        cells.append(text_normalizer(cell) if cell["type"] == "text" else normalize_logo_cell(cell))

    return cells


def build_header_cells_for_template(
    template_id: str,
    *,
    existing_cells: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Monta células do cabeçalho para o modelo informado, preservando conteúdo compatível."""
    if template_id not in HEADER_TEMPLATE_IDS:
        raise ValidationError("Modelo de cabeçalho inválido.")
    return _build_band_cells_for_template(
        HEADER_TEMPLATE_SPECS,
        template_id,
        existing_cells=existing_cells,
        text_normalizer=normalize_text_cell,
    )


def build_footer_cells_for_template(
    template_id: str,
    *,
    existing_cells: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Monta células do rodapé para o modelo informado, preservando conteúdo compatível."""
    if template_id not in FOOTER_TEMPLATE_IDS:
        raise ValidationError("Modelo de rodapé inválido.")
    return _build_band_cells_for_template(
        FOOTER_TEMPLATE_SPECS,
        template_id,
        existing_cells=existing_cells,
        text_normalizer=normalize_footer_text_cell,
    )


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
        "indent_level": normalize_indent_level(cell.get("indent_level", 0)),
        "first_line_indent": bool(cell.get("first_line_indent", False)),
    }


def normalize_header_extra_text_row(row: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza linha de texto extra do cabeçalho."""
    normalized = normalize_text_cell(row)
    normalized["muted"] = bool(row.get("muted", False))
    return normalized


def normalize_header_extra_rule_row(row: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza linha horizontal extra do cabeçalho."""
    if row.get("type") != HEADER_EXTRA_ROW_TYPE_RULE:
        raise ValidationError("Linha extra de cabeçalho inválida.")
    return {"type": HEADER_EXTRA_ROW_TYPE_RULE}


def normalize_header_extra_row(row: Any) -> dict[str, Any]:
    """Normaliza uma linha extra abaixo da faixa principal do cabeçalho."""
    if not isinstance(row, dict):
        raise ValidationError("Cada linha extra do cabeçalho deve ser um objeto.")

    row_type = row.get("type")
    if row_type == HEADER_EXTRA_ROW_TYPE_TEXT:
        return normalize_header_extra_text_row(row)
    if row_type == HEADER_EXTRA_ROW_TYPE_RULE:
        return normalize_header_extra_rule_row(row)
    raise ValidationError("Tipo de linha extra de cabeçalho inválido.")


def normalize_header_extra_rows(rows: Any) -> list[dict[str, Any]]:
    """Normaliza linhas extras de largura total do cabeçalho."""
    if rows in (None, ""):
        return []
    if not isinstance(rows, list):
        raise ValidationError("Linhas extras do cabeçalho devem ser uma lista.")
    if len(rows) > MAX_HEADER_EXTRA_ROWS:
        raise ValidationError(
            f"O cabeçalho aceita no máximo {MAX_HEADER_EXTRA_ROWS} linhas extras."
        )
    return [normalize_header_extra_row(row) for row in rows]


def normalize_footer_text_cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza célula de texto do rodapé."""
    normalized = normalize_text_cell(cell)
    if "show_page_number" in cell:
        normalized["show_page_number"] = bool(cell["show_page_number"])
    else:
        normalized["show_page_number"] = True
    return normalized


def footer_text_cell_shows_page_number(cell: dict[str, Any]) -> bool:
    """Indica se a célula de texto do rodapé deve exibir numeração no PDF."""
    if cell.get("type") != "text":
        return False
    return bool(cell.get("show_page_number", False))


def normalize_footer_cell(cell: Any) -> dict[str, Any]:
    """Normaliza uma célula do rodapé."""
    if not isinstance(cell, dict):
        raise ValidationError("Cada célula do rodapé deve ser um objeto.")
    cell_type = cell.get("type")
    if cell_type == "logo":
        return normalize_logo_cell(cell)
    if cell_type == "text":
        return normalize_footer_text_cell(cell)
    raise ValidationError("Tipo de célula de rodapé inválido.")


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
        return _disabled_band_layout()

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
    extra_rows = normalize_header_extra_rows(header.get("extra_rows", []))

    return {
        "enabled": True,
        "template_id": template_id,
        "column_widths": column_widths,
        "cells": cells,
        "extra_rows": extra_rows,
    }


def normalize_footer_layout(footer: Any) -> dict[str, Any]:
    """Normaliza payload do rodapé de página."""
    if not isinstance(footer, dict):
        raise ValidationError("Rodapé deve ser um objeto JSON.")

    enabled = bool(footer.get("enabled", False))
    template_id = footer.get("template_id")
    cells_payload = footer.get("cells", [])
    column_widths_payload = footer.get("column_widths", [])

    if not enabled:
        return _disabled_band_layout()

    if template_id not in FOOTER_TEMPLATE_IDS:
        raise ValidationError("Informe um modelo de rodapé válido.")

    if not isinstance(cells_payload, list):
        raise ValidationError("Células do rodapé devem ser uma lista.")

    spec = FOOTER_TEMPLATE_SPECS[template_id]
    expected_len = len(spec["cells"])
    if len(cells_payload) != expected_len:
        cells_payload = build_footer_cells_for_template(template_id)

    cells = [normalize_footer_cell(cell) for cell in cells_payload]
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


def merge_page_layout(
    existing: dict[str, Any] | None,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """Mescla atualização parcial de layout preservando faixas não enviadas."""
    current = normalize_page_layout(existing)
    if "header" in incoming:
        current["header"] = normalize_header_layout(incoming["header"])
    if "footer" in incoming:
        current["footer"] = normalize_footer_layout(incoming["footer"])
    return current


def normalize_page_layout(payload: Any) -> dict[str, Any]:
    """Normaliza layout completo de página do relatório."""
    from reports.services.report_kind import REPORTLINE_META_KEY

    if payload in (None, ""):
        return default_page_layout()
    if not isinstance(payload, dict):
        raise ValidationError("Layout de página deve ser um objeto JSON.")

    header = normalize_header_layout(payload.get("header", _disabled_band_layout()))
    footer = normalize_footer_layout(payload.get("footer", _disabled_band_layout()))
    normalized: dict[str, Any] = {"header": header, "footer": footer}

    meta = payload.get(REPORTLINE_META_KEY)
    if isinstance(meta, dict):
        normalized[REPORTLINE_META_KEY] = dict(meta)

    return normalized


def apply_header_template(
    page_layout: dict[str, Any] | None,
    template_id: str,
) -> dict[str, Any]:
    """Ativa cabeçalho com o modelo informado."""
    if template_id not in HEADER_TEMPLATE_IDS:
        raise ValidationError("Modelo de cabeçalho inválido.")

    current = normalize_page_layout(page_layout)
    existing_cells = current["header"].get("cells", [])
    existing_extra_rows = current["header"].get("extra_rows", [])
    spec = HEADER_TEMPLATE_SPECS[template_id]

    current["header"] = {
        "enabled": True,
        "template_id": template_id,
        "column_widths": list(spec["column_widths"]),
        "cells": build_header_cells_for_template(
            template_id,
            existing_cells=existing_cells,
        ),
        "extra_rows": normalize_header_extra_rows(existing_extra_rows),
    }
    return current


def apply_footer_template(
    page_layout: dict[str, Any] | None,
    template_id: str,
) -> dict[str, Any]:
    """Ativa rodapé com o modelo informado."""
    if template_id not in FOOTER_TEMPLATE_IDS:
        raise ValidationError("Modelo de rodapé inválido.")

    current = normalize_page_layout(page_layout)
    existing_cells = current["footer"].get("cells", [])
    spec = FOOTER_TEMPLATE_SPECS[template_id]

    current["footer"] = {
        "enabled": True,
        "template_id": template_id,
        "column_widths": list(spec["column_widths"]),
        "cells": build_footer_cells_for_template(
            template_id,
            existing_cells=existing_cells,
        ),
    }
    return current


def enrich_band_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Acrescenta URL pública às células de logo para templates."""
    from django.core.files.storage import default_storage

    enriched: list[dict[str, Any]] = []
    for cell in cells:
        item = dict(cell)
        if item.get("type") == "logo" and item.get("file"):
            item["url"] = default_storage.url(item["file"])
        enriched.append(item)
    return enriched


enrich_header_cells = enrich_band_cells


def enrich_page_layout_for_editor(page_layout: dict[str, Any] | None) -> dict[str, Any]:
    """Prepara layout de página para renderização no editor."""
    normalized = normalize_page_layout(page_layout)

    header = normalized["header"]
    if header.get("enabled"):
        header = dict(header)
        header["cells"] = enrich_band_cells(header.get("cells", []))
        header["template_label"] = HEADER_TEMPLATE_LABELS.get(
            header.get("template_id"),
            "",
        )
        normalized = dict(normalized)
        normalized["header"] = header

    footer = normalized["footer"]
    if footer.get("enabled"):
        footer = dict(footer)
        footer["cells"] = enrich_band_cells(footer.get("cells", []))
        footer["template_label"] = FOOTER_TEMPLATE_LABELS.get(
            footer.get("template_id"),
            "",
        )
        normalized = dict(normalized)
        normalized["footer"] = footer

    return normalized


def _update_band_logo_cell_from_image(
    page_layout: dict[str, Any],
    *,
    band: str,
    cell_index: int,
    image_payload: dict[str, Any],
) -> dict[str, Any]:
    """Atualiza célula de logo de cabeçalho ou rodapé após upload."""
    normalized = normalize_page_layout(page_layout)
    band_layout = normalized[band]
    band_label = "Cabeçalho" if band == "header" else "Rodapé"

    if not band_layout.get("enabled"):
        raise ValidationError(f"{band_label} não está ativo.")

    cells = [dict(cell) for cell in band_layout["cells"]]
    if cell_index < 0 or cell_index >= len(cells):
        raise ValidationError("Índice de célula de logo inválido.")
    if cells[cell_index].get("type") != "logo":
        raise ValidationError("A célula informada não é de logo.")

    logo_slot = cells[cell_index].get("logo_slot", "primary")
    display_width_override = image_payload.get("display_width")
    display_height_override = image_payload.get("display_height")
    if display_width_override is not None and display_height_override is not None:
        display_width = max(1, int(display_width_override))
        display_height = max(1, int(display_height_override))
    else:
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
    band_layout = dict(band_layout)
    band_layout["cells"] = cells
    normalized = dict(normalized)
    normalized[band] = band_layout
    return normalized


def clear_band_logo_cell(
    page_layout: dict[str, Any] | None,
    *,
    band: str,
    cell_index: int,
) -> dict[str, Any]:
    """Esvazia célula de logo do cabeçalho ou rodapé."""
    if band not in ("header", "footer"):
        raise ValidationError("Faixa de layout inválida.")

    normalized = normalize_page_layout(page_layout)
    band_layout = normalized[band]
    band_label = "Cabeçalho" if band == "header" else "Rodapé"

    if not band_layout.get("enabled"):
        raise ValidationError(f"{band_label} não está ativo.")

    cells = [dict(cell) for cell in band_layout["cells"]]
    if cell_index < 0 or cell_index >= len(cells):
        raise ValidationError("Índice de célula de logo inválido.")
    if cells[cell_index].get("type") != "logo":
        raise ValidationError("A célula informada não é de logo.")

    logo_slot = cells[cell_index].get("logo_slot", "primary")
    cells[cell_index] = normalize_logo_cell(default_logo_cell(logo_slot=logo_slot))
    band_layout = dict(band_layout)
    band_layout["cells"] = cells
    normalized = dict(normalized)
    normalized[band] = band_layout
    return normalized


def update_logo_cell_from_image(
    page_layout: dict[str, Any],
    *,
    cell_index: int,
    image_payload: dict[str, Any],
) -> dict[str, Any]:
    """Atualiza célula de logo do cabeçalho após upload de imagem."""
    return _update_band_logo_cell_from_image(
        page_layout,
        band="header",
        cell_index=cell_index,
        image_payload=image_payload,
    )


def update_footer_logo_cell_from_image(
    page_layout: dict[str, Any],
    *,
    cell_index: int,
    image_payload: dict[str, Any],
) -> dict[str, Any]:
    """Atualiza célula de logo do rodapé após upload de imagem."""
    return _update_band_logo_cell_from_image(
        page_layout,
        band="footer",
        cell_index=cell_index,
        image_payload=image_payload,
    )
