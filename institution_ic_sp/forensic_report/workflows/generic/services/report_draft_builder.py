"""
Montagem do rascunho inicial de laudo pericial genérico.

Cria ``Report`` com cabeçalho institucional e árvore de blocos
padronizada para edição imediata no editor de relatórios.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.institution_page_layout import (
    build_institution_page_layout,
    get_examiner_assignment_labels,
)
from institution_ic_sp.forensic_report.services.preamble import build_preamble_paragraph
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_block_alignment import default_text_align_for_block
from reports.services.report_block_content import normalize_block_content
from reports.services.report_creation import create_report

CLOSING_PHRASE = "É o que havia a relatar."


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

    block = ReportBlock.objects.create(**block_kwargs)
    return ReportNode.objects.create(
        report=report,
        block=block,
        position=Decimal(str(position)),
    )


def _signature_paragraph(examiner: ForensicExaminerSP) -> str:
    """Monta bloco textual de assinatura com dados do perfil pericial."""
    lines: list[str] = []
    display_name = examiner.display_name.strip() or examiner.user.get_full_name().strip()
    if display_name:
        lines.append(display_name)
    if examiner.job_title:
        lines.append(examiner.get_job_title_display())
    unit_label, _city = get_examiner_assignment_labels(examiner)
    if unit_label:
        lines.append(unit_label)
    if not lines:
        lines.append("Assinatura do perito")
    return "\n".join(lines)


def _list_content(items: list[str]) -> dict:
    """Monta payload de lista com marcadores."""
    if items:
        return {"items": items}
    return {"items": [""]}


@transaction.atomic
def build_generic_forensic_report_draft(
    *,
    author: AbstractBaseUser,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
) -> Report:
    """
    Gera laudo pericial genérico em rascunho com estrutura padronizada.

    Persiste cabeçalho/rodapé institucionais, título principal, preâmbulo,
    seções administrativas e fechamento com campo de assinatura.
    """
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    report = create_report(author=author, title=metadata.list_title)

    page_layout = build_institution_page_layout(
        report,
        institution=institution,
        examiner=examiner,
        workflow=GENERIC_WORKFLOW.slug,
    )
    report.page_layout = page_layout
    report.save(update_fields=["page_layout", "updated_at"])

    position = 1
    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.HEADING,
        content={"text": metadata.main_title_text},
        title_level=0,
        is_main_title=True,
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.PARAGRAPH,
        content={"text": build_preamble_paragraph(metadata)},
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.HEADING,
        content={"text": "Objetivo do Exame"},
        title_level=1,
    )
    position += 1

    objective_text = metadata.exam_objective.strip()
    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.PARAGRAPH,
        content={"text": objective_text},
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.HEADING,
        content={"text": "Dados da Requisição"},
        title_level=1,
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.UNORDERED_LIST,
        content=_list_content(metadata.requisition_list_items()),
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.HEADING,
        content={"text": "Dados do Atendimento"},
        title_level=1,
    )
    position += 1

    unit_label, city_label = get_examiner_assignment_labels(examiner)
    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.UNORDERED_LIST,
        content=_list_content(
            metadata.attendance_list_items(
                unit_label=unit_label,
                city_label=city_label,
            )
        ),
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.PARAGRAPH,
        content={"text": ""},
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.PARAGRAPH,
        content={"text": CLOSING_PHRASE},
    )
    position += 1

    _create_report_node(
        report,
        position=position,
        block_type=ReportBlockType.PARAGRAPH,
        content={"text": _signature_paragraph(examiner)},
        text_align="right",
        first_line_indent=False,
    )

    return report
