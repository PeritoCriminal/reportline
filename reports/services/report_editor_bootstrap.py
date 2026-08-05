"""
Bootstrap inicial do editor de relatório.

Garante que relatórios sem nós possuam um título H1 vazio
pronto para edição imediata.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from institution_ic_sp.forensic_report.services.forensic_bootstrap import is_forensic_bootstrap_pending
from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_block_alignment import default_text_align_for_block
from reports.services.report_block_content import default_content_for_block_type


@transaction.atomic
def ensure_editor_bootstrap(report: Report) -> ReportNode | None:
    """
    Cria nó inicial com título vazio quando o relatório não possui blocos.

    Retorna o nó criado ou ``None`` se a árvore já possuir conteúdo.
    """
    if report.nodes.exists():
        return None

    if is_forensic_bootstrap_pending(report):
        return None

    block = ReportBlock.objects.create(
        block_type=ReportBlockType.HEADING,
        content=default_content_for_block_type(ReportBlockType.HEADING),
        title_level=0,
        text_align=default_text_align_for_block(
            ReportBlockType.HEADING,
            is_main_title=True,
        ),
    )
    return ReportNode.objects.create(
        report=report,
        block=block,
        position=Decimal("1"),
    )
