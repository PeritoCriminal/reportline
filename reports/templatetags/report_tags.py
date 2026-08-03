"""
Tags de template para listagem e exibição de relatórios.
"""

from django import template

from reports.services.report_kind import is_forensic_report

register = template.Library()


@register.filter(name="is_forensic_report")
def is_forensic_report_filter(report) -> bool:
    """Indica se o relatório é um laudo pericial gerado pelo fluxo IC-SP."""
    return is_forensic_report(report)
