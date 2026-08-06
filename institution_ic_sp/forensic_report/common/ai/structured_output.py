"""
Conversão de JSON inferido pela IA para ``CaseMetadata``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.exam_category import normalize_exam_category
from institution_ic_sp.forensic_report.common.services.case_metadata import (
    CaseMetadata,
    normalize_case_metadata,
    normalize_text_field,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    _parse_date,
    _parse_datetime,
)


def _clean_ai_str(value: Any, *, field_name: str = "") -> str:
    """Normaliza string retornada pela IA."""
    if value is None:
        return ""
    cleaned = str(value).strip()
    if field_name:
        return normalize_text_field(field_name, cleaned)
    return cleaned


def _parse_ai_date(value: Any) -> date | None:
    """Interpreta data retornada pela IA."""
    raw = _clean_ai_str(value)
    if not raw:
        return None
    parsed = _parse_date(raw)
    if parsed is not None:
        return parsed
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_ai_datetime(value: Any) -> datetime | None:
    """Interpreta data/hora retornada pela IA."""
    raw = _clean_ai_str(value)
    if not raw:
        return None
    parsed = _parse_datetime(raw)
    if parsed is not None:
        return parsed
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed_iso = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timezone.is_naive(parsed_iso):
        return timezone.make_aware(parsed_iso, timezone.get_current_timezone())
    return parsed_iso


def _parse_ai_year(value: Any) -> int:
    """Interpreta ano retornado pela IA."""
    if isinstance(value, int):
        return value
    raw = _clean_ai_str(value)
    return int(raw) if raw.isdigit() else 0


def _normalize_extension_value(value: Any) -> Any:
    """Converte valor de ``extensions`` para tipo JSON persistível."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        normalized_items = [_normalize_extension_value(item) for item in value]
        return [item for item in normalized_items if item is not None and item != ""]
    if isinstance(value, dict):
        return extensions_from_ai_payload({"extensions": value})
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def extensions_from_ai_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """
    Extrai e normaliza o objeto ``extensions`` retornado pela IA.

    Ignora chaves vazias e valores não serializáveis; converte escalares
    desconhecidos em string.
    """
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("extensions")
    if not isinstance(raw, dict):
        return {}

    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        cleaned_key = str(key).strip()
        if not cleaned_key:
            continue
        normalized_value = _normalize_extension_value(value)
        if normalized_value is None:
            continue
        if normalized_value == "":
            continue
        if isinstance(normalized_value, (list, dict)) and not normalized_value:
            continue
        normalized[cleaned_key] = normalized_value
    return normalized


def case_metadata_from_ai_payload(payload: dict[str, Any]) -> CaseMetadata:
    """Mapeia objeto JSON da IA para dataclass de metadados do intake."""
    return normalize_case_metadata(
        CaseMetadata(
            report_number=_clean_ai_str(payload.get("report_number"), field_name="report_number"),
            report_year=_parse_ai_year(payload.get("report_year")),
            designation_date=_parse_ai_date(payload.get("designation_date")),
            exam_objective=_clean_ai_str(payload.get("exam_objective"), field_name="exam_objective"),
            exam_category=normalize_exam_category(payload.get("exam_category")),
            requesting_authority=_clean_ai_str(
                payload.get("requesting_authority"),
                field_name="requesting_authority",
            ),
            police_district=_clean_ai_str(
                payload.get("police_district"),
                field_name="police_district",
            ),
            occurrence_report=_clean_ai_str(
                payload.get("occurrence_report"),
                field_name="occurrence_report",
            ),
            police_inquiry=_clean_ai_str(payload.get("police_inquiry"), field_name="police_inquiry"),
            occurrence_at=_parse_ai_datetime(payload.get("occurrence_at")),
            requisition_at=_parse_ai_datetime(payload.get("requisition_at")),
            attendance_protocol=_clean_ai_str(
                payload.get("attendance_protocol"),
                field_name="attendance_protocol",
            ),
            examiner=_clean_ai_str(payload.get("examiner"), field_name="examiner"),
            examination_at=_parse_ai_datetime(payload.get("examination_at")),
            photography=_clean_ai_str(payload.get("photography"), field_name="photography"),
            scanning_3d=_clean_ai_str(payload.get("scanning_3d"), field_name="scanning_3d"),
            sketch=_clean_ai_str(payload.get("sketch"), field_name="sketch"),
        )
    )
