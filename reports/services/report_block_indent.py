"""
Recuo de parágrafos no editor e na renderização do laudo.

Define níveis de recuo de bloco (0–5), recuo de primeira linha conforme
padrão tipográfico em português e validação por tipo de bloco.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from reports.models import ReportBlockType, ReportNode
from reports.models.report_block import ReportBlockLineSpacing

MAX_INDENT_LEVEL = 5

INDENTABLE_BLOCK_TYPES = frozenset({
    ReportBlockType.PARAGRAPH,
    ReportBlockType.ORDERED_LIST,
    ReportBlockType.UNORDERED_LIST,
})


def normalize_indent_level(value, *, default: int = 0) -> int:
    """Valida nível de recuo de bloco ou retorna o padrão informado."""
    if value in (None, ""):
        return default
    try:
        level = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Nível de recuo inválido.") from exc
    if level < 0 or level > MAX_INDENT_LEVEL:
        raise ValidationError(f"O recuo deve estar entre 0 e {MAX_INDENT_LEVEL}.")
    return level


def default_indent_level_for_block(
    block_type: str,
    *,
    is_caption: bool = False,
) -> int:
    """Parágrafos de corpo iniciam sem recuo de bloco; demais tipos também."""
    if block_type == ReportBlockType.PARAGRAPH and not is_caption:
        return 0
    return 0


def default_first_line_indent_for_block(
    block_type: str,
    *,
    is_caption: bool = False,
    report_first_line_indent: bool | None = None,
) -> bool:
    """Parágrafos de corpo usam recuo de primeira linha conforme config do laudo."""
    if is_caption:
        return False
    if block_type == ReportBlockType.PARAGRAPH:
        if report_first_line_indent is not None:
            return report_first_line_indent
        return True
    return False


def is_caption_paragraph_node(node: ReportNode) -> bool:
    """Indica parágrafo imediatamente após bloco de imagem (legenda)."""
    from reports.services.report_editor_context import is_caption_paragraph_node as _is_caption

    return _is_caption(node)


def resolve_indent_on_create(
    block_type: str,
    *,
    is_caption: bool = False,
    indent_level: int | None = None,
    first_line_indent: bool | None = None,
    report_first_line_indent: bool | None = None,
) -> tuple[int, bool]:
    """Resolve nível e recuo de 1ª linha ao criar bloco, com herança opcional."""
    level = (
        normalize_indent_level(indent_level)
        if indent_level is not None
        else default_indent_level_for_block(block_type, is_caption=is_caption)
    )
    first_line = (
        bool(first_line_indent)
        if first_line_indent is not None
        else default_first_line_indent_for_block(
            block_type,
            is_caption=is_caption,
            report_first_line_indent=report_first_line_indent,
        )
    )
    return level, first_line


def normalize_line_spacing(
    value,
    *,
    default: str = ReportBlockLineSpacing.NORMAL,
) -> str:
    """Valida espaçamento entre linhas do bloco ou retorna o padrão informado."""
    if value in (None, ""):
        return default
    cleaned = str(value).strip().lower()
    valid = {choice.value for choice in ReportBlockLineSpacing}
    if cleaned not in valid:
        raise ValidationError("Espaçamento entre linhas inválido.")
    return cleaned


def validate_paragraph_indent_patch(
    node: ReportNode,
    *,
    indent_level: int | None,
    first_line_indent: bool | None,
    line_spacing: str | None = None,
) -> None:
    """Garante que alterações de recuo respeitem o tipo de bloco."""
    if indent_level is None and first_line_indent is None and line_spacing is None:
        return

    block = node.block
    if block.block_type not in INDENTABLE_BLOCK_TYPES:
        raise ValidationError("Recuo aplica-se somente a parágrafos e listas.")

    if block.block_type != ReportBlockType.PARAGRAPH:
        if first_line_indent is not None or line_spacing is not None:
            raise ValidationError(
                "Recuo de primeira linha e espaçamento aplicam-se somente a parágrafos."
            )

    if block.block_type == ReportBlockType.PARAGRAPH and is_caption_paragraph_node(node):
        raise ValidationError("Legendas de imagem não aceitam recuo.")


def apply_paragraph_indent_patch(
    node: ReportNode,
    *,
    indent_level: int | None,
    first_line_indent: bool | None,
    line_spacing: str | None = None,
) -> list[str]:
    """Atualiza campos de recuo e espaçamento do bloco e retorna campos alterados."""
    validate_paragraph_indent_patch(
        node,
        indent_level=indent_level,
        first_line_indent=first_line_indent,
        line_spacing=line_spacing,
    )

    block = node.block
    update_fields: list[str] = []

    if indent_level is not None:
        block.indent_level = normalize_indent_level(indent_level)
        update_fields.append("indent_level")

    if first_line_indent is not None:
        block.first_line_indent = bool(first_line_indent)
        update_fields.append("first_line_indent")

    if line_spacing is not None:
        block.line_spacing = normalize_line_spacing(line_spacing)
        update_fields.append("line_spacing")

    return update_fields
