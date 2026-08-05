"""
Cobertura de campos inferidos pela IA no bootstrap pericial.

Classifica o que a extração identificou (texto, data ou data/hora parcial)
para decidir prompts pendentes e valores padrão no formulário inline.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.utils import timezone

from institution_ic_sp.forensic_report.common.ai.structured_output import (
    _parse_ai_date,
    _parse_ai_datetime,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata

TEXT_PROMPT_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "report_number",
        "exam_objective",
        "requesting_authority",
        "police_district",
        "occurrence_report",
        "police_inquiry",
        "attendance_protocol",
        "photography",
        "scanning_3d",
        "sketch",
    }
)

DATE_PROMPT_FIELD_NAMES: frozenset[str] = frozenset({"designation_date"})

DATETIME_PROMPT_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "occurrence_at",
        "requisition_at",
        "examination_at",
    }
)

ALL_PROMPT_FIELD_NAMES: frozenset[str] = (
    TEXT_PROMPT_FIELD_NAMES | DATE_PROMPT_FIELD_NAMES | DATETIME_PROMPT_FIELD_NAMES
)


def classify_datetime_raw(raw: Any) -> str:
    """
    Classifica cobertura de datetime inferido pela IA.

    Retorna ``missing``, ``date_only`` (só data) ou ``datetime`` (data e hora).
    """
    if raw is None:
        return "missing"
    cleaned = str(raw).strip()
    if not cleaned:
        return "missing"
    if "T" not in cleaned and " " not in cleaned and len(cleaned) <= 10:
        return "date_only"
    if "T" in cleaned:
        time_part = cleaned.split("T", 1)[1]
        if not time_part or time_part.startswith("00:00"):
            return "date_only"
    if " " in cleaned:
        time_part = cleaned.split(" ", 1)[1]
        if not time_part or time_part.startswith("00:00"):
            return "date_only"
    return "datetime"


def build_field_coverage_from_ai_payload(payload: dict[str, Any] | None) -> dict[str, str]:
    """Monta mapa de cobertura por campo a partir do JSON bruto da IA."""
    if not payload:
        return {}

    coverage: dict[str, str] = {}
    for field_name in TEXT_PROMPT_FIELD_NAMES:
        raw = payload.get(field_name)
        coverage[field_name] = "full" if str(raw or "").strip() else "missing"

    for field_name in DATE_PROMPT_FIELD_NAMES:
        coverage[field_name] = "full" if _parse_ai_date(payload.get(field_name)) else "missing"

    for field_name in DATETIME_PROMPT_FIELD_NAMES:
        coverage[field_name] = classify_datetime_raw(payload.get(field_name))

    return coverage


def merge_field_coverage_with_metadata(
    metadata: CaseMetadata,
    coverage: dict[str, str],
) -> dict[str, str]:
    """
    Marca campos já preenchidos nos metadados finais como cobertos.

    Impede prompt quando o perito ou a mesclagem já trouxe valor, inclusive
    data sem hora inferida pela IA (hora 00:00 implícita).
    """
    merged = dict(coverage)
    for field_name in TEXT_PROMPT_FIELD_NAMES:
        if str(getattr(metadata, field_name, "") or "").strip():
            merged[field_name] = "full"

    if metadata.designation_date is not None:
        merged["designation_date"] = "full"

    for field_name in DATETIME_PROMPT_FIELD_NAMES:
        value = getattr(metadata, field_name, None)
        if value is None:
            continue
        if merged.get(field_name) == "date_only":
            continue
        merged[field_name] = "datetime"

    return merged


def default_prompt_value(field_name: str) -> str:
    """Valor inicial sugerido para inputs de prompt quando a IA não identificou."""
    today = timezone.localdate()
    if field_name in DATE_PROMPT_FIELD_NAMES:
        return today.isoformat()
    if field_name in DATETIME_PROMPT_FIELD_NAMES:
        return f"{today.isoformat()}T00:00"
    return ""


def is_prompt_field_value_empty(metadata: CaseMetadata, field_name: str) -> bool:
    """Indica se campo elegível a prompt permanece vazio nos metadados."""
    if field_name in DATE_PROMPT_FIELD_NAMES:
        return metadata.designation_date is None
    if field_name in DATETIME_PROMPT_FIELD_NAMES:
        return getattr(metadata, field_name, None) is None
    return not str(getattr(metadata, field_name, "") or "").strip()
