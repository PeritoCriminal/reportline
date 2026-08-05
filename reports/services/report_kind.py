"""
Identificação de laudos periciais via metadados em ``page_layout``.

Evita model ou migration dedicados: o marcador persiste no JSON
existente do relatório e sobrevive à normalização de layout.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from reports.models import Report

REPORTLINE_META_KEY = "reportline_meta"
FORENSIC_REPORT_KIND = "forensic_report"
INSTITUTIONAL_PAGE_LAYOUT_SNAPSHOT_KEY = "institutional_page_layout_snapshot"


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


def institutional_page_layout_snapshot(page_layout: dict[str, Any] | None) -> dict[str, Any] | None:
    """Retorna cópia congelada de cabeçalho e rodapé institucionais, se existir."""
    if not isinstance(page_layout, dict):
        return None
    meta = page_layout.get(REPORTLINE_META_KEY, {})
    if not isinstance(meta, dict):
        return None
    snapshot = meta.get(INSTITUTIONAL_PAGE_LAYOUT_SNAPSHOT_KEY)
    return deepcopy(snapshot) if isinstance(snapshot, dict) else None


def attach_institutional_page_layout_snapshot(page_layout: dict[str, Any]) -> dict[str, Any]:
    """
    Congela cabeçalho e rodapé atuais em ``reportline_meta``.

    Usado na criação do laudo pericial para permitir restauração posterior
    sem reler cadastros institucionais ou periciais.
    """
    merged = dict(page_layout)
    meta = dict(merged.get(REPORTLINE_META_KEY, {}))
    meta[INSTITUTIONAL_PAGE_LAYOUT_SNAPSHOT_KEY] = {
        "header": deepcopy(page_layout["header"]),
        "footer": deepcopy(page_layout["footer"]),
    }
    merged[REPORTLINE_META_KEY] = meta
    return merged


def ensure_institutional_page_layout_snapshot(report: Report) -> bool:
    """
    Preenche snapshot ausente em laudos periciais legados.

    Retorna ``True`` quando o relatório foi persistido com novo snapshot.
    """
    if not is_forensic_report(report):
        return False
    if institutional_page_layout_snapshot(report.page_layout):
        return False

    from reports.services.report_page_layout import normalize_page_layout

    normalized = normalize_page_layout(report.page_layout)
    report.page_layout = attach_institutional_page_layout_snapshot(normalized)
    report.save(update_fields=["page_layout", "updated_at"])
    return True
