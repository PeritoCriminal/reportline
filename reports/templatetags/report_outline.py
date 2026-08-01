"""
Filtros de template para o sumário do editor de relatórios.
"""

from __future__ import annotations

from uuid import UUID

from django import template

from reports.services.report_editor_context import ReportOutlineEntry

register = template.Library()


@register.filter
def outline_list_reorderable(entries) -> bool:
    """
    Indica se a lista de entradas pode ser reordenada via arrastar e soltar.

    Exige ao menos dois títulos irmãos reais (mesmo ``report_parent_id``),
    independentemente da hierarquia visual por ``title_level``.
    """
    if not entries or len(entries) < 2:
        return False
    parent_ids: set[UUID | None] = set()
    for entry in entries:
        if not isinstance(entry, ReportOutlineEntry):
            return False
        parent_ids.add(entry.report_parent_id)
    return len(parent_ids) == 1


@register.filter
def outline_sibling_parent_id(entries) -> str:
    """Retorna o ``report_parent_id`` compartilhado pela lista de irmãos reais."""
    if not entries:
        return ""
    entry = entries[0]
    if not isinstance(entry, ReportOutlineEntry):
        return ""
    if entry.report_parent_id is None:
        return ""
    return str(entry.report_parent_id)
