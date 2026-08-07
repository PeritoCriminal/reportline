# reportline/reports/services/report_inline_text.py
"""
Sanitização de HTML inline para campos de texto editáveis.

Permite negrito, itálico, sublinhado, riscado, sobrescrito, subscrito e links inline nos blocos
do laudo, eliminando tags e atributos não permitidos antes da persistência.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

ALLOWED_INLINE_TAGS = frozenset({"strong", "em", "u", "s", "a", "sup", "sub", "span"})
ALLOWED_INLINE_FONT_SIZE_CLASSES = frozenset({
    "report-inline-font-xs",
    "report-inline-font-sm",
    "report-inline-font-md",
    "report-inline-font-lg",
})
ALLOWED_INLINE_FONT_FAMILY_CLASSES = frozenset({
    "report-inline-font-serif",
})
INLINE_FONT_SIZE_CLASS_PRIORITY = (
    "report-inline-font-xs",
    "report-inline-font-sm",
    "report-inline-font-md",
    "report-inline-font-lg",
)
ALLOWED_LINK_PREFIXES = ("http://", "https://", "mailto:")
BLOCKED_LINK_PREFIXES = ("javascript:", "data:", "vbscript:")
BLOCK_TAGS = frozenset({"p", "div"})
TAG_ALIASES = {
    "b": "strong",
    "i": "em",
    "strike": "s",
    "del": "s",
}


def resolve_inline_font_span_classes(class_names: str) -> str | None:
    """Monta classes permitidas de tamanho e família tipográfica para ``span`` inline."""
    tokens = class_names.split()
    size_classes = {
        name for name in tokens if name in ALLOWED_INLINE_FONT_SIZE_CLASSES
    }
    family_classes = {
        name for name in tokens if name in ALLOWED_INLINE_FONT_FAMILY_CLASSES
    }
    if not size_classes and not family_classes:
        return None

    resolved: list[str] = []
    for size_class in INLINE_FONT_SIZE_CLASS_PRIORITY:
        if size_class in size_classes:
            resolved.append(size_class)
            break
    if "report-inline-font-serif" in family_classes:
        resolved.append("report-inline-font-serif")
    return " ".join(resolved) if resolved else None


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


def _normalize_plain_text_line_breaks(value: str) -> str:
    """Converte quebras de linha literais em ``<br>`` para texto sem tags HTML."""
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" not in normalized:
        return normalized
    return "<br>".join(normalized.split("\n"))


class _InlineTextSanitizer(HTMLParser):
    """Reconstrói HTML permitindo somente formatação inline segura."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._tag_stack: list[str] = []

    def _append_block_break_if_needed(self) -> None:
        """Insere ``<br>`` antes de blocos ``div``/``p`` quando já há conteúdo."""
        if self._parts and not self._parts[-1].endswith("<br>"):
            self._parts.append("<br>")

    def handle_starttag(self, tag: str, attrs) -> None:
        normalized = TAG_ALIASES.get(tag.lower(), tag.lower())
        if normalized == "br":
            self._parts.append("<br>")
            return
        if normalized in BLOCK_TAGS:
            self._append_block_break_if_needed()
            return
        if normalized == "span":
            class_names = dict(attrs).get("class", "")
            font_classes = resolve_inline_font_span_classes(class_names)
            if not font_classes:
                return
            self._tag_stack.append(normalized)
            self._parts.append(f'<span class="{font_classes}">')
            return

        if normalized == "a":
            attrs_dict = dict(attrs)
            href = normalize_inline_link_href(attrs_dict.get("href", ""))
            if not href:
                return
            self._tag_stack.append(normalized)
            link_attrs = f'href="{escape(href, quote=True)}"'
            if href.lower().startswith(("http://", "https://")):
                link_attrs += ' target="_blank" rel="noopener noreferrer"'
            self._parts.append(f"<a {link_attrs}>")
            return

        if normalized not in ALLOWED_INLINE_TAGS:
            return
        self._tag_stack.append(normalized)
        self._parts.append(f"<{normalized}>")

    def handle_endtag(self, tag: str) -> None:
        normalized = TAG_ALIASES.get(tag.lower(), tag.lower())
        if normalized not in ALLOWED_INLINE_TAGS:
            return
        matched = False
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == normalized:
                del self._tag_stack[index:]
                matched = True
                break
        if matched:
            self._parts.append(f"</{normalized}>")

    def handle_data(self, data: str) -> None:
        normalized = data.replace("\r\n", "\n").replace("\r", "\n")
        if "\n" not in normalized:
            self._parts.append(escape(normalized))
            return

        lines = normalized.split("\n")
        for index, line in enumerate(lines):
            self._parts.append(escape(line))
            if index < len(lines) - 1:
                self._parts.append("<br>")

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def get_html(self) -> str:
        """Fecha tags abertas e retorna HTML sanitizado."""
        while self._tag_stack:
            tag = self._tag_stack.pop()
            self._parts.append(f"</{tag}>")
        html = "".join(self._parts)
        while html.endswith("<br>"):
            html = html[:-4]
        return html


class _HeaderTextSanitizer(_InlineTextSanitizer):
    """Alias do sanitizador inline; cabeçalho usa a mesma normalização de quebras."""


def sanitize_header_text_html(value: str) -> str:
    """
    Sanitiza HTML de célula de texto do cabeçalho.

    Permite formatação inline e quebras de linha via ``<br>``; blocos ``p``/``div``
    são normalizados para quebras de linha.
    """
    if not isinstance(value, str):
        return ""
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return _normalize_plain_text_line_breaks(value)

    parser = _HeaderTextSanitizer()
    parser.feed(value)
    parser.close()
    return parser.get_html()


def sanitize_inline_text_html(value: str) -> str:
    """
    Remove markup perigoso e normaliza tags de formatação inline.

    Texto sem tags permanece inalterado, exceto quebras de linha literais
    convertidas em ``<br>``; blocos ``div``/``p`` viram quebras suaves equivalentes
    a Shift+Enter no editor.
    """
    if not isinstance(value, str):
        return ""
    if not value:
        return ""
    if "<" not in value and ">" not in value:
        return _normalize_plain_text_line_breaks(value)

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
