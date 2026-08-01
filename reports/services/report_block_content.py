"""
Normalização e conteúdo padrão de blocos de relatório.

Valida payloads JSON por ``block_type`` antes da persistência
nas operações interativas do editor.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from reports.models import ReportBlockType


def default_content_for_block_type(block_type: str) -> dict[str, Any]:
    """Retorna payload JSON inicial vazio conforme o tipo de bloco."""
    if block_type == ReportBlockType.HEADING:
        return {"text": ""}
    if block_type == ReportBlockType.PARAGRAPH:
        return {"text": ""}
    if block_type in (ReportBlockType.ORDERED_LIST, ReportBlockType.UNORDERED_LIST):
        return {"items": [""]}
    if block_type == ReportBlockType.LINK:
        return {"text": "", "url": ""}
    if block_type == ReportBlockType.TABLE:
        return {"headers": [], "rows": [], "show_borders": True, "show_header": True, "column_widths": []}
    if block_type == ReportBlockType.IMAGE:
        return {"alt": "", "file": "", "image_id": "", "width": 0, "height": 0}
    raise ValidationError("Tipo de bloco não suportado.")


def build_empty_table_content(row_count: int, column_count: int) -> dict[str, Any]:
    """
    Monta payload vazio de tabela com dimensões informadas.

    A primeira linha corresponde ao cabeçalho; ``row_count`` inclui essa linha.
    """
    rows = max(1, min(int(row_count), 20))
    cols = max(1, min(int(column_count), 12))
    empty_cell = {
        "type": "text",
        "text": "",
        "align": "left",
    }
    from reports.services.report_table_column_widths import equal_column_widths

    return {
        "headers": [{"text": "", "align": "left"} for _ in range(cols)],
        "rows": [[empty_cell.copy() for _ in range(cols)] for _ in range(rows - 1)],
        "show_borders": True,
        "show_header": True,
        "column_widths": equal_column_widths(cols),
    }


def normalize_block_content(block_type: str, content: Any) -> dict[str, Any]:
    """
    Normaliza e valida o payload ``content`` para o tipo informado.

    Levanta ``ValidationError`` quando a estrutura não corresponde ao tipo.
    """
    if not isinstance(content, dict):
        raise ValidationError("Conteúdo do bloco deve ser um objeto JSON.")

    if block_type in (ReportBlockType.HEADING, ReportBlockType.PARAGRAPH):
        text = content.get("text", "")
        if not isinstance(text, str):
            raise ValidationError("O campo text deve ser texto.")
        return {"text": text}

    if block_type in (ReportBlockType.ORDERED_LIST, ReportBlockType.UNORDERED_LIST):
        items = content.get("items", [])
        if not isinstance(items, list):
            raise ValidationError("O campo items deve ser uma lista.")
        return {"items": [str(item) for item in items]}

    if block_type == ReportBlockType.LINK:
        text = content.get("text", "")
        url = content.get("url", "")
        if not isinstance(text, str) or not isinstance(url, str):
            raise ValidationError("Link exige text e url como texto.")
        return {"text": text, "url": url}

    if block_type == ReportBlockType.TABLE:
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        if not isinstance(headers, list) or not isinstance(rows, list):
            raise ValidationError("Tabela exige headers e rows como listas.")

        from reports.services.report_table_cell_content import (
            normalize_table_body_cell,
            normalize_table_header_cell,
        )
        from reports.services.report_table_column_widths import normalize_column_widths

        normalized_headers = [normalize_table_header_cell(header) for header in headers]
        column_count = len(normalized_headers)
        normalized_rows = []
        for row in rows:
            if not isinstance(row, list):
                raise ValidationError("Cada linha da tabela deve ser uma lista.")
            cells = [normalize_table_body_cell(cell) for cell in row][:column_count]
            while len(cells) < column_count:
                cells.append({"type": "text", "text": "", "align": "left"})
            normalized_rows.append(cells)

        show_borders = content.get("show_borders", True)
        if not isinstance(show_borders, bool):
            raise ValidationError("O campo show_borders deve ser verdadeiro ou falso.")

        show_header = content.get("show_header", True)
        if not isinstance(show_header, bool):
            raise ValidationError("O campo show_header deve ser verdadeiro ou falso.")

        column_widths = normalize_column_widths(content.get("column_widths"), column_count)

        return {
            "headers": normalized_headers,
            "rows": normalized_rows,
            "show_borders": show_borders,
            "show_header": show_header,
            "column_widths": column_widths,
        }

    if block_type == ReportBlockType.IMAGE:
        alt = content.get("alt", "")
        file_ref = content.get("file", "")
        image_id = content.get("image_id", "")
        width = content.get("width", 0)
        height = content.get("height", 0)
        if not isinstance(alt, str) or not isinstance(file_ref, str):
            raise ValidationError("Imagem exige alt e file como texto.")
        if image_id is not None and not isinstance(image_id, (str, int)):
            raise ValidationError("Imagem exige image_id como texto.")
        if not isinstance(width, int) or not isinstance(height, int):
            raise ValidationError("Imagem exige width e height inteiros.")
        return {
            "alt": alt,
            "file": file_ref,
            "image_id": str(image_id) if image_id else "",
            "width": max(0, width),
            "height": max(0, height),
        }

    raise ValidationError("Tipo de bloco não suportado.")
