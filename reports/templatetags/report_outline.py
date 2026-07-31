"""
Filtros de template para o sumário do editor de relatórios.
"""

from __future__ import annotations

from uuid import UUID

from django import template

from reports.services.report_editor_context import ReportOutlineEntry

register = template.Library()


def _normalize_parent_id(raw_parent_id) -> UUID | None:
    """Converte valor de template em UUID de pai ou None para raiz."""
    if raw_parent_id in (None, ""):
        return None
    if isinstance(raw_parent_id, UUID):
        return raw_parent_id
    return UUID(str(raw_parent_id))


@register.filter
def outline_list_reorderable(entries, parent_node_id) -> bool:
    """
    Indica se a lista de entradas pode ser reordenada via arrastar e soltar.

    Exige ao menos dois títulos irmãos reais (mesmo ``report_parent_id``).
    """
    if not entries or len(entries) < 2:
        return False
    expected_parent_id = _normalize_parent_id(parent_node_id)
    for entry in entries:
        if not isinstance(entry, ReportOutlineEntry):
            return False
        if entry.report_parent_id != expected_parent_id:
            return False
    return True
