# reportline/institution_ic_sp/forensic_report/services/forensic_report_body_builder.py
"""
Montagem do corpo padronizado de laudo pericial genérico.

Centraliza criação de blocos e mapa semântico de nós para bootstrap
interativo e geração completa do rascunho inicial.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_block_alignment import default_text_align_for_block
from reports.services.report_block_content import normalize_block_content
from reports.services.report_inline_text import sanitize_header_text_html
from reports.services.report_tree import delete_node

CLOSING_PHRASE = "Nada mais havendo a consignar, encerra-se o presente laudo."
CLOSING_DIGITAL_ARCHIVE_NOTICE = (
    "Laudo assinado digitalmente e arquivado no sistema GDL da Superintendência "
    "da Polícia Técnico-Científica do Estado de São Paulo."
)


def _create_report_node(
    report: Report,
    *,
    position: int,
    block_type: str,
    content: dict,
    title_level: int = 0,
    is_main_title: bool = False,
    text_align: str | None = None,
    first_line_indent: bool | None = None,
    indent_level: int | None = None,
    line_spacing: str | None = None,
) -> ReportNode:
    """Cria bloco e nó raiz na posição informada."""
    if text_align is None:
        text_align = default_text_align_for_block(
            block_type,
            title_level=title_level,
            is_main_title=is_main_title,
        )

    block_kwargs = {
        "block_type": block_type,
        "content": normalize_block_content(block_type, content),
        "title_level": title_level,
        "text_align": text_align,
    }
    if first_line_indent is not None:
        block_kwargs["first_line_indent"] = first_line_indent
    if indent_level is not None:
        block_kwargs["indent_level"] = indent_level
    if line_spacing is not None:
        block_kwargs["line_spacing"] = line_spacing

    block = ReportBlock.objects.create(**block_kwargs)
    return ReportNode.objects.create(
        report=report,
        block=block,
        position=Decimal(str(position)),
    )


def _wrap_preamble_text(text: str) -> str:
    """Envolve o preâmbulo em fonte 10 pt serifada para renderização no laudo."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    return (
        f'<span class="report-inline-font-xs report-inline-font-serif">{cleaned}</span>'
    )


def _wrap_italic_text(text: str) -> str:
    """Envolve texto do fechamento em itálico para renderização no laudo."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    return f"<em>{cleaned}</em>"


def _examiner_display_name_text(examiner: ForensicExaminerSP) -> str:
    """Retorna nome de exibição do perito para a assinatura do laudo."""
    display_name = examiner.display_name.strip() or examiner.user.get_full_name().strip()
    return display_name or "Assinatura do perito"


def _examiner_job_title_text(examiner: ForensicExaminerSP) -> str:
    """Retorna cargo do perito para a assinatura do laudo."""
    if examiner.job_title:
        return examiner.get_job_title_display()
    return "Perito Criminal"


def _examiner_signature_text(examiner: ForensicExaminerSP) -> str:
    """Monta assinatura do perito com quebra suave entre nome e cargo."""
    return f"{_examiner_display_name_text(examiner)}<br>{_examiner_job_title_text(examiner)}"


def _append_section_with_optional_list(
    report: Report,
    *,
    position: int,
    heading: str,
    list_items: list[str],
    node_registry: dict[str, str],
    heading_key: str,
    list_key: str,
) -> int:
    """Insere título de seção e lista, registrando IDs semânticos."""
    heading_node = _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.HEADING,
        content={"text": heading},
        title_level=0,
    )
    node_registry[heading_key] = str(heading_node.pk)
    position += 1

    if list_items:
        list_node = _create_report_node(
            report,
            position=position,
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": list_items},
        )
        node_registry[list_key] = str(list_node.pk)
        position += 1

    return position


def clear_report_body_nodes(report: Report) -> None:
    """Remove todos os nós do laudo antes de remontar o corpo."""
    nodes = list(report.nodes.select_related("block").order_by("created_at"))
    for node in nodes:
        delete_node(node)


def update_header_report_number(page_layout: dict, metadata: CaseMetadata) -> dict:
    """Atualiza linha do número do laudo abaixo do cabeçalho institucional."""
    layout = dict(page_layout)
    header = layout.get("header")
    if not isinstance(header, dict):
        return layout

    extra_rows = header.get("extra_rows")
    if not isinstance(extra_rows, list) or len(extra_rows) < 2:
        return layout

    extra_rows = list(extra_rows)
    report_number_row = dict(extra_rows[1])
    report_number_row["text"] = sanitize_header_text_html(
        f'<span class="report-inline-font-sm">{metadata.header_report_number_text}</span>'
    )
    extra_rows[1] = report_number_row
    header = dict(header)
    header["extra_rows"] = extra_rows
    layout["header"] = header
    return layout


@transaction.atomic
def populate_forensic_report_body(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
    institution: Institution | None = None,
    replace_existing: bool = True,
) -> dict[str, str]:
    """
    Monta corpo padronizado do laudo pericial e retorna mapa semântico de nós.

    Quando ``replace_existing`` é verdadeiro, remove nós anteriores do laudo.
    """
    institution = institution or Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
        run_all_forensic_body_steps,
    )

    return run_all_forensic_body_steps(
        report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        replace_existing=replace_existing,
    )
