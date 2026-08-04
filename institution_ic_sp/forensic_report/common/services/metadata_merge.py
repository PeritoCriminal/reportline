"""
Mescla metadados manuais e inferidos priorizando valores informados pelo perito.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date, datetime
from typing import Any

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata


def _is_empty(value: Any) -> bool:
    """Indica se valor deve ser substituído pela inferência."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, int) and value == 0:
        return True
    return False


def merge_case_metadata(manual: CaseMetadata, inferred: CaseMetadata) -> CaseMetadata:
    """
    Combina metadados preservando campos preenchidos manualmente.

    Para cada atributo, usa o valor manual quando presente; caso contrário,
    adota o valor inferido pela IA (ou stub).
    """
    merged: dict[str, Any] = {}
    for field in fields(CaseMetadata):
        manual_value = getattr(manual, field.name)
        inferred_value = getattr(inferred, field.name)
        if _is_empty(manual_value):
            merged[field.name] = inferred_value
        else:
            merged[field.name] = manual_value
    return CaseMetadata(**merged)
