"""
Conversão entre ``CaseMetadata`` e estruturas usadas no intake HTTP.
"""

from __future__ import annotations

from datetime import date, datetime

from django.http import QueryDict
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata

DATETIME_INPUT_FORMATS = (
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def _clean_str(value: object) -> str:
    """Normaliza valor textual opcional vindo do POST."""
    if value is None:
        return ""
    return str(value).strip()


def _parse_date(raw: str) -> date | None:
    """Converte string de data para ``date``."""
    if not raw:
        return None
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(raw: str) -> datetime | None:
    """Converte string de data/hora para ``datetime`` com fuso quando necessário."""
    if not raw:
        return None
    for fmt in DATETIME_INPUT_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
        except ValueError:
            continue
    return None


def case_metadata_from_post(post: QueryDict) -> CaseMetadata:
    """Monta metadados parciais a partir dos campos atuais do formulário."""
    year_raw = _clean_str(post.get("report_year"))
    report_year = int(year_raw) if year_raw.isdigit() else 0

    return CaseMetadata(
        report_number=_clean_str(post.get("report_number")),
        report_year=report_year,
        designation_date=_parse_date(_clean_str(post.get("designation_date"))),
        exam_objective=_clean_str(post.get("exam_objective")),
        supplementary_prompt=_clean_str(post.get("supplementary_prompt")),
        requesting_authority=_clean_str(post.get("requesting_authority")),
        police_district=_clean_str(post.get("police_district")),
        occurrence_report=_clean_str(post.get("occurrence_report")),
        police_inquiry=_clean_str(post.get("police_inquiry")),
        occurrence_at=_parse_datetime(_clean_str(post.get("occurrence_at"))),
        requisition_at=_parse_datetime(_clean_str(post.get("requisition_at"))),
        attendance_protocol=_clean_str(post.get("attendance_protocol")),
        examiner=_clean_str(post.get("examiner")),
        examination_at=_parse_datetime(_clean_str(post.get("examination_at"))),
        photography=_clean_str(post.get("photography")),
        scanning_3d=_clean_str(post.get("scanning_3d")),
        sketch=_clean_str(post.get("sketch")),
    )


def _format_date(value: date | None) -> str:
    """Formata data para input HTML ``date``."""
    return value.isoformat() if value else ""


def _format_datetime(value: datetime | None) -> str:
    """Formata datetime para input HTML ``datetime-local``."""
    if value is None:
        return ""
    localized = timezone.localtime(value) if timezone.is_aware(value) else value
    return localized.strftime("%Y-%m-%dT%H:%M")


def case_metadata_to_form_dict(metadata: CaseMetadata) -> dict[str, str | int]:
    """Serializa metadados para preenchimento do formulário via JSON."""
    return {
        "report_number": metadata.report_number,
        "report_year": metadata.report_year or "",
        "designation_date": _format_date(metadata.designation_date),
        "exam_objective": metadata.exam_objective,
        "supplementary_prompt": metadata.supplementary_prompt,
        "requesting_authority": metadata.requesting_authority,
        "police_district": metadata.police_district,
        "occurrence_report": metadata.occurrence_report,
        "police_inquiry": metadata.police_inquiry,
        "occurrence_at": _format_datetime(metadata.occurrence_at),
        "requisition_at": _format_datetime(metadata.requisition_at),
        "attendance_protocol": metadata.attendance_protocol,
        "examiner": metadata.examiner,
        "examination_at": _format_datetime(metadata.examination_at),
        "photography": metadata.photography,
        "scanning_3d": metadata.scanning_3d,
        "sketch": metadata.sketch,
    }
