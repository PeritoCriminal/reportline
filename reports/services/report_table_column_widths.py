# reportline/reports/services/report_table_column_widths.py
"""
Larguras de colunas em tabelas do editor.

Persiste percentuais inteiros (soma 100) e expõe utilitários para
normalização e mutações estruturais (inserir/excluir/redimensionar).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

MIN_COLUMN_WIDTH_PERCENT = 5


def resolve_table_column_count(content: dict[str, Any]) -> int:
    """
    Infere o número de colunas a partir de cabeçalhos, linhas ou larguras.

    Usa o maior valor disponível para evitar truncar o corpo quando o
    cabeçalho está ausente ou incompleto (ex.: tabela de localização com QR).
    """
    header_count = 0
    headers = content.get("headers", [])
    if isinstance(headers, list) and headers:
        header_count = len(headers)

    body_count = 0
    rows = content.get("rows", [])
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list) and row:
                body_count = max(body_count, len(row))

    width_count = 0
    column_widths = content.get("column_widths", [])
    if isinstance(column_widths, list) and column_widths:
        width_count = len(column_widths)

    return max(header_count, body_count, width_count)


def equal_column_widths(column_count: int) -> list[int]:
    """Distribui 100% igualmente entre ``column_count`` colunas."""
    if column_count <= 0:
        return []

    base, remainder = divmod(100, column_count)
    return [base + (1 if index < remainder else 0) for index in range(column_count)]


def _coerce_width(value: Any) -> int:
    """Converte valor bruto em percentual inteiro positivo."""
    try:
        width = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Larguras de coluna devem ser números inteiros.") from exc

    if width < 1:
        raise ValidationError("Cada largura de coluna deve ser ao menos 1%.")
    return width


def normalize_column_widths(raw_widths: Any, column_count: int) -> list[int]:
    """
    Normaliza lista de larguras para ``column_count`` colunas somando 100%.

    Recalcula proporcionalmente quando a soma difere ou a lista está ausente.
    """
    if column_count <= 0:
        return []

    if not isinstance(raw_widths, list) or len(raw_widths) != column_count:
        return equal_column_widths(column_count)

    widths = [_coerce_width(value) for value in raw_widths]
    total = sum(widths)
    if total <= 0:
        return equal_column_widths(column_count)

    if total == 100:
        return widths

    scaled = [max(1, round(width * 100 / total)) for width in widths]
    diff = 100 - sum(scaled)
    if diff != 0:
        scaled[-1] = max(1, scaled[-1] + diff)
    return normalize_column_widths(scaled, column_count)


def split_column_width(widths: list[int], col_index: int) -> list[int]:
    """Divide a largura da coluna ``col_index`` ao inserir coluna à direita."""
    if col_index < 0 or col_index >= len(widths):
        raise ValidationError("Índice de coluna inválido.")

    next_widths = list(widths)
    current = next_widths[col_index]
    left = current // 2
    right = current - left
    next_widths[col_index] = left
    next_widths.insert(col_index + 1, right)
    return normalize_column_widths(next_widths, len(next_widths))


def merge_column_width(widths: list[int], col_index: int) -> list[int]:
    """Reincorpora largura da coluna removida no vizinho mais próximo."""
    if col_index < 0 or col_index >= len(widths):
        raise ValidationError("Índice de coluna inválido.")

    if len(widths) <= 1:
        raise ValidationError("A tabela deve manter ao menos uma coluna.")

    next_widths = list(widths)
    removed = next_widths.pop(col_index)
    target_index = col_index if col_index < len(next_widths) else len(next_widths) - 1
    next_widths[target_index] += removed
    return normalize_column_widths(next_widths, len(next_widths))


def resize_adjacent_columns(
    widths: list[int],
    left_index: int,
    delta_percent: int,
    *,
    min_percent: int = MIN_COLUMN_WIDTH_PERCENT,
) -> list[int]:
    """
    Transfere ``delta_percent`` da coluna à direita para a esquerda.

    Valores positivos de ``delta`` aumentam a coluna esquerda; negativos diminuem.
    """
    if left_index < 0 or left_index >= len(widths) - 1:
        raise ValidationError("Índice de coluna inválido para redimensionamento.")

    next_widths = list(widths)
    left = next_widths[left_index]
    right = next_widths[left_index + 1]

    left_next = left + delta_percent
    right_next = right - delta_percent

    if left_next < min_percent or right_next < min_percent:
        max_delta = min(left - min_percent, right - min_percent)
        if max_delta <= 0:
            return widths
        delta_percent = max(-max_delta, min(max_delta, delta_percent))
        left_next = left + delta_percent
        right_next = right - delta_percent

    next_widths[left_index] = left_next
    next_widths[left_index + 1] = right_next
    return normalize_column_widths(next_widths, len(next_widths))
