"""
Sanitização de HTML inline para campos de texto editáveis.

Permite negrito, itálico, sublinhado, riscado e links inline nos blocos
do laudo, eliminando tags e atributos não permitidos antes da persistência.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

ALLOWED_INLINE_TAGS = frozenset({"strong", "em", "u", "s", "a"})
ALLOWED_LINK_PREFIXES = ("http://", "https://", "mailto:")
BLOCKED_LINK_PREFIXES = ("javascript:", "data:", "vbscript:")
TAG_ALIASES = {
    "b": "strong",
    "i": "em",
    "strike": "s",
    "del": "s",
}


def normalize_inline_link_href(href: str) -> str | None:
    """
    Normaliza URL de link inline ou retorna None se vazia ou perigosa.

    Endereços sem esquema recebem ``https://``; e-mails recebem ``mailto:``.
    """
    if not isinstance(href, str):
        return None

    cleaned = href.strip()
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if lowered.startswith(BLOCKED_LINK_PREFIXES):
        return None

    if lowered.startswith(ALLOWED_LINK_PREFIXES):
        return cleaned

    if "@" in cleaned and not lowered.startswith("mailto:"):
        return f"mailto:{cleaned}"

    return f"https://{cleaned.lstrip('/')}"


class _InlineTextSanitizer(HTMLParser):
    """Reconstrói HTML permitindo somente formatação inline segura."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = TAG_ALIASES.get(tag.lower(), tag.lower())
        if normalized == "a":
            href = normalize_inline_link_href(dict(attrs).get("href", ""))
            if not href:
                return
            self._tag_stack.append(normalized)
            self._parts.append(f'<a href="{escape(href, quote=True)}">')
            return

        if normalized not in ALLOWED_INLINE_TAGS:
            return
        self._tag_stack.append(normalized)
        self._parts.append(f"<{normalized}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = TAG_ALIASES.get(tag.lower(), tag.lower())
        if normalized not in ALLOWED_INLINE_TAGS:
            return
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == normalized:
                del self._tag_stack[index:]
                break
        self._parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        self._parts.append(escape(data))

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def get_html(self) -> str:
        """Fecha tags abertas e retorna HTML sanitizado."""
        while self._tag_stack:
            tag = self._tag_stack.pop()
            self._parts.append(f"</{tag}>")
        return "".join(self._parts)


def sanitize_inline_text_html(value: str) -> str:
    """
    Remove markup perigoso e normaliza tags de formatação inline.

    Texto sem tags permanece inalterado; entidades HTML são preservadas.
    """
    if not isinstance(value, str):
        return ""
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return value

    parser = _InlineTextSanitizer()
    parser.feed(value)
    parser.close()
    return parser.get_html()


def inline_text_plain(value: str) -> str:
    """Extrai texto visível de HTML inline sanitizado para rótulos e sumário."""
    if not isinstance(value, str) or not value:
        return ""
    if "<" not in value and ">" not in value:
        return value

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    parser = _TextExtractor()
    parser.feed(sanitize_inline_text_html(value))
    parser.close()
    return "".join(parser.parts)
