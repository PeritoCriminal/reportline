# reportline/reports/services/report_block_alignment.py
"""
Alinhamento de blocos e células no editor de relatório.

Define valores válidos, normalização e padrões por tipo de bloco
conforme regras editoriais do laudo.
"""

from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError

from reports.models import Report, ReportBlockType, ReportNode

TEXT_ALIGN_VALUES = frozenset({"left", "center", "right", "justify"})


def normalize_text_align(value, *, default: str = "left") -> str:
    """Valida alinhamento textual ou retorna o padrão informado."""
    if value in (None, ""):
        return default
    if value not in TEXT_ALIGN_VALUES:
        raise ValidationError("Alinhamento de texto inválido.")
    return value


def report_has_heading(report: Report) -> bool:
    """Indica se o relatório já possui ao menos um bloco de título."""
    return ReportNode.objects.filter(
        report=report,
        block__block_type=ReportBlockType.HEADING,
    ).exists()


def is_main_title_heading_node(report: Report, node: ReportNode) -> bool:
    """Indica se o nó é o título principal do relatório (sem numeração)."""
    from reports.services.report_heading_numbering import build_heading_number_map_for_report

    if node.block.block_type != ReportBlockType.HEADING:
        return False

    numbers = build_heading_number_map_for_report(report)
    return numbers.get(node.pk) == ""


def is_main_title_heading_insertion(
    report: Report,
    *,
    before_node: ReportNode | None = None,
    after_node: ReportNode | None = None,
) -> bool:
    """
    Indica se um novo título na posição informada será o título principal.

    O título principal é o primeiro título do relatório, exibido sem numeração.
    """
    if not report_has_heading(report):
        return True

    if before_node is not None:
        return is_main_title_heading_node(report, before_node)

    return False


def demote_previous_main_title(report: Report, before_node: ReportNode) -> None:
    """Rebaixa alinhamento do antigo título principal ao inserir um novo acima."""
    if not is_main_title_heading_node(report, before_node):
        return

    block = before_node.block
    if block.text_align == "center":
        block.text_align = "left"
        block.save(update_fields=["text_align", "updated_at"])


def default_text_align_for_block(
    block_type: str,
    *,
    title_level: int = 0,
    is_caption: bool = False,
    is_main_title: bool = False,
) -> str:
    """
    Retorna alinhamento padrão conforme tipo e metadados do bloco.

    Somente o título principal (sem numeração) fica centralizado; demais
    títulos, inclusive numerados de qualquer nível, alinham à esquerda.
    """
    if block_type == ReportBlockType.HEADING:
        return "center" if is_main_title else "left"
    if block_type == ReportBlockType.PARAGRAPH:
        return "center" if is_caption else "justify"
    if block_type in (
        ReportBlockType.ORDERED_LIST,
        ReportBlockType.UNORDERED_LIST,
    ):
        return "left"
    if block_type == ReportBlockType.IMAGE:
        return "center"
    if block_type == ReportBlockType.LINK:
        return "justify"
    if block_type == ReportBlockType.TABLE:
        return "left"
    if block_type == ReportBlockType.HORIZONTAL_RULE:
        return "center"
    return "left"


def default_text_align_for_table_header() -> str:
    """Cabeçalhos de tabela alinhados à esquerda por padrão."""
    return "left"


def default_text_align_for_table_cell(cell_type: str = "text") -> str:
    """Imagens em célula centralizadas; texto à esquerda."""
    if cell_type == "image":
        return "center"
    return "left"


def realign_heading_defaults_for_report(report: Report) -> None:
    """Atualiza alinhamento padrão de títulos conforme numeração do relatório."""
    from reports.services.report_heading_numbering import build_heading_number_map_for_report

    numbers = build_heading_number_map_for_report(report)
    for node in report.nodes.select_related("block").filter(
        block__block_type=ReportBlockType.HEADING,
    ):
        expected = "center" if numbers.get(node.pk) == "" else "left"
        if node.block.text_align != expected:
            node.block.text_align = expected
            node.block.save(update_fields=["text_align", "updated_at"])
