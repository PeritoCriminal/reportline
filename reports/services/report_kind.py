"""
Identificação de laudos periciais via metadados em ``page_layout``.

Evita model ou migration dedicados: o marcador persiste no JSON
existente do relatório e sobrevive à normalização de layout.
"""

from __future__ import annotations

from reports.models import Report

REPORTLINE_META_KEY = "reportline_meta"
FORENSIC_REPORT_KIND = "forensic_report"


def is_forensic_report(report: Report) -> bool:
    """Indica se o relatório foi gerado pelo fluxo de laudo pericial."""
    meta = (report.page_layout or {}).get(REPORTLINE_META_KEY, {})
    return isinstance(meta, dict) and meta.get("kind") == FORENSIC_REPORT_KIND


def is_forensic_report_layout(page_layout: dict | None) -> bool:
    """Indica se um layout de página pertence a laudo pericial."""
    if not isinstance(page_layout, dict):
        return False
    meta = page_layout.get(REPORTLINE_META_KEY, {})
    return isinstance(meta, dict) and meta.get("kind") == FORENSIC_REPORT_KIND


def forensic_report_meta(*, workflow: str) -> dict[str, dict[str, str]]:
    """Monta metadados de laudo pericial para inclusão em ``page_layout``."""
    return {
        REPORTLINE_META_KEY: {
            "kind": FORENSIC_REPORT_KIND,
            "workflow": workflow,
        },
    }


def merge_reportline_meta(
    page_layout: dict,
    *,
    workflow: str,
) -> dict:
    """Anexa metadados de laudo pericial a um layout de página existente."""
    merged = dict(page_layout)
    merged.update(forensic_report_meta(workflow=workflow))
    return merged
