"""
Context processors do app reports.

Expõe flags de desenvolvimento para templates do editor.
"""

from django.conf import settings


def report_editor_dev(request):
    """Disponibiliza atalhos temporários do editor apenas em DEBUG."""
    return {
        "report_editor_dev_ipsum": settings.DEBUG,
    }
