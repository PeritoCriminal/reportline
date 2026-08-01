"""
Operações estruturais em tabelas do editor (linhas e colunas).

Insere ou remove linhas/colunas relativas à célula focada, respeitando
limites de dimensão do editor.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.core.exceptions import ValidationError

from reports.models import ReportBlockType
from reports.services.report_block_content import normalize_block_content

MAX_TABLE_BODY_ROWS = 19
MAX_TABLE_COLUMNS = 12
MIN_TABLE_BODY_ROWS = 1
MIN_TABLE_COLUMNS = 1


def _empty_body_cell() -> dict[str, str]:
    """Retorna célula de corpo vazia normalizada."""
    return {"type": "text", "text": ""}


def _column_count(content: dict[str, Any]) -> int:
    """Retorna número de colunas a partir dos cabeçalhos."""
    return len(content.get("headers", []))


def _normalize_table(content: dict[str, Any]) -> dict[str, Any]:
    """Normaliza payload completo de tabela."""
    return normalize_block_content(ReportBlockType.TABLE, content)


def insert_row_after(content: dict[str, Any], row_index: int) -> dict[str, Any]:
    """
    Insere linha vazia após ``row_index`` (0-based no corpo, abaixo do cabeçalho).

    ``row_index`` referencia a linha do corpo onde está o cursor; a nova linha
    aparece imediatamente abaixo.
    """
    payload = deepcopy(content)
    rows = list(payload.get("rows", []))
    if not rows:
        rows = [[_empty_body_cell()]]

    if row_index < -1 or row_index >= len(rows):
        raise ValidationError("Índice de linha inválido.")

    if len(rows) >= MAX_TABLE_BODY_ROWS:
        raise ValidationError(f"A tabela não pode exceder {MAX_TABLE_BODY_ROWS} linhas de corpo.")

    column_count = _column_count(payload) or len(rows[max(row_index, 0)])
    new_row = [_empty_body_cell() for _ in range(column_count)]
    insert_at = 0 if row_index < 0 else row_index + 1
    rows.insert(insert_at, new_row)
    payload["rows"] = rows
    return _normalize_table(payload)


def delete_row(content: dict[str, Any], row_index: int) -> dict[str, Any]:
    """Remove linha do corpo na posição informada."""
    payload = deepcopy(content)
    rows = list(payload.get("rows", []))

    if row_index < 0 or row_index >= len(rows):
        raise ValidationError("Índice de linha inválido.")

    if len(rows) <= MIN_TABLE_BODY_ROWS:
        raise ValidationError("A tabela deve manter ao menos uma linha de corpo.")

    rows.pop(row_index)
    payload["rows"] = rows
    return _normalize_table(payload)


def insert_column_after(content: dict[str, Any], col_index: int) -> dict[str, Any]:
    """Insere coluna vazia após ``col_index`` (0-based)."""
    payload = deepcopy(content)
    headers = list(payload.get("headers", []))
    rows = list(payload.get("rows", []))

    if not headers:
        headers = [""]

    if col_index < 0 or col_index >= len(headers):
        raise ValidationError("Índice de coluna inválido.")

    if len(headers) >= MAX_TABLE_COLUMNS:
        raise ValidationError(f"A tabela não pode exceder {MAX_TABLE_COLUMNS} colunas.")

    headers.insert(col_index + 1, "")
    new_rows = []
    for row in rows:
        row_cells = list(row)
        row_cells.insert(col_index + 1, _empty_body_cell())
        new_rows.append(row_cells)

    while len(new_rows) < MIN_TABLE_BODY_ROWS:
        new_rows.append([_empty_body_cell() for _ in range(len(headers))])

    payload["headers"] = headers
    payload["rows"] = new_rows
    return _normalize_table(payload)


def delete_column(content: dict[str, Any], col_index: int) -> dict[str, Any]:
    """Remove coluna na posição informada."""
    payload = deepcopy(content)
    headers = list(payload.get("headers", []))
    rows = list(payload.get("rows", []))

    if col_index < 0 or col_index >= len(headers):
        raise ValidationError("Índice de coluna inválido.")

    if len(headers) <= MIN_TABLE_COLUMNS:
        raise ValidationError("A tabela deve manter ao menos uma coluna.")

    headers.pop(col_index)
    payload["headers"] = headers
    payload["rows"] = [
        [cell for index, cell in enumerate(row) if index != col_index]
        for row in rows
    ]
    return _normalize_table(payload)
