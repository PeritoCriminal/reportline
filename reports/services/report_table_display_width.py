# reportline/reports/services/report_table_display_width.py
"""
Largura de exibição de tabelas no editor.

Persiste percentual da área útil do bloco (10–100), independente das
larguras relativas entre colunas.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

MIN_TABLE_DISPLAY_WIDTH = 20
MAX_TABLE_DISPLAY_WIDTH = 100
DEFAULT_TABLE_DISPLAY_WIDTH = 100


def normalize_display_width(raw_width: Any) -> int:
    """Normaliza largura de exibição da tabela em percentual inteiro."""
    if raw_width in (None, ""):
        return DEFAULT_TABLE_DISPLAY_WIDTH

    try:
        width = int(raw_width)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "A largura da tabela deve ser um número inteiro."
        ) from exc

    if width < MIN_TABLE_DISPLAY_WIDTH or width > MAX_TABLE_DISPLAY_WIDTH:
        raise ValidationError(
            f"A largura da tabela deve estar entre "
            f"{MIN_TABLE_DISPLAY_WIDTH}% e {MAX_TABLE_DISPLAY_WIDTH}%."
        )
    return width
