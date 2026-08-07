# reportline/reports/templatetags/report_inline_text.py
"""Filtros de template para exibição segura de texto inline formatado."""

from django import template
from django.utils.safestring import mark_safe

from reports.services.report_inline_text import (
    sanitize_header_text_html,
    sanitize_inline_text_html,
)

register = template.Library()


@register.filter
def inline_text(value) -> str:
    """Sanitiza HTML inline e retorna markup seguro para templates."""
    if not value:
        return ""
    return mark_safe(sanitize_inline_text_html(str(value)))


@register.filter
def header_text(value) -> str:
    """Sanitiza HTML de cabeçalho (inline + quebras de linha) para templates."""
    if not value:
        return ""
    return mark_safe(sanitize_header_text_html(str(value)))
