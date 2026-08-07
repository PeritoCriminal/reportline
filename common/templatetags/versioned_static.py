# reportline/common/templatetags/versioned_static.py
"""
Tags de template para arquivos estáticos com invalidação de cache em DEBUG.
"""

from __future__ import annotations

import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path: str) -> str:
    """
    Retorna URL estática com parâmetro de versão baseado no mtime do arquivo.

    Em DEBUG, evita que o navegador reutilize CSS/JS obsoletos entre recargas
    normais (F5) durante o desenvolvimento local.
    """
    url = static(path)
    if not settings.DEBUG:
        return url

    absolute_path = finders.find(path)
    if not absolute_path:
        return url

    version = int(os.path.getmtime(absolute_path))
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}v={version}"
