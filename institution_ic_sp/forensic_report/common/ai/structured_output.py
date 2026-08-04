"""
Conversão de JSON inferido pela IA para ``CaseMetadata``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    _parse_date,
    _parse_datetime,
)


def _clean_ai_str(value: Any) -> str:
    """Normaliza string retornada pela IA."""
    if value is None:
        return ""
    return str(value).strip()


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


def case_metadata_from_ai_payload(payload: dict[str, Any]) -> CaseMetadata:
    """Mapeia objeto JSON da IA para dataclass de metadados do intake."""
    return CaseMetadata(
        report_number=_clean_ai_str(payload.get("report_number")),
        report_year=_parse_ai_year(payload.get("report_year")),
        designation_date=_parse_ai_date(payload.get("designation_date")),
        exam_objective=_clean_ai_str(payload.get("exam_objective")),
        requesting_authority=_clean_ai_str(payload.get("requesting_authority")),
        police_district=_clean_ai_str(payload.get("police_district")),
        occurrence_report=_clean_ai_str(payload.get("occurrence_report")),
        police_inquiry=_clean_ai_str(payload.get("police_inquiry")),
        occurrence_at=_parse_ai_datetime(payload.get("occurrence_at")),
        requisition_at=_parse_ai_datetime(payload.get("requisition_at")),
        attendance_protocol=_clean_ai_str(payload.get("attendance_protocol")),
        examiner=_clean_ai_str(payload.get("examiner")),
        examination_at=_parse_ai_datetime(payload.get("examination_at")),
        photography=_clean_ai_str(payload.get("photography")),
        scanning_3d=_clean_ai_str(payload.get("scanning_3d")),
        sketch=_clean_ai_str(payload.get("sketch")),
    )
