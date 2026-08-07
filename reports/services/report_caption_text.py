# reportline/reports/services/report_caption_text.py
"""
Normalização de texto de legendas de imagem em laudos.

Remove prefixos de numeração que a IA ou o perito possam incluir por engano,
pois o ReportLine numera figuras nativamente quando ``number_captions`` está ativo.
"""

from __future__ import annotations

import re

_FIGURE_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"[Ff]igura|[Ff]IG\.?"
    r")\s*\d+\s*"
    r"(?:[-–—:]\s*|\.\s+)?",
    re.UNICODE,
)


def strip_figure_prefix_from_caption(text: str) -> str:
    """
    Remove prefixo ``Figura N`` (ou variantes) do início da legenda.

    O editor e o PDF adicionam a numeração automaticamente; o texto persistido
    deve conter apenas o corpo descritivo da legenda.
    """
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _FIGURE_PREFIX_RE.sub("", cleaned, count=1).strip()
    return cleaned


def normalize_caption_text(text: str) -> str:
    """Normaliza legenda para persistência em bloco nativo de parágrafo-legenda."""
    return strip_figure_prefix_from_caption(text)
