"""
Bootstrap inicial do editor de relatório.

Garante que relatórios sem nós possuam um título H1 vazio
pronto para edição imediata.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.services.report_block_content import default_content_for_block_type


@transaction.atomic
def ensure_editor_bootstrap(report: Report) -> ReportNode | None:
    """
    Cria nó inicial com título vazio quando o relatório não possui blocos.

    Retorna o nó criado ou ``None`` se a árvore já possuir conteúdo.
    """
    if report.nodes.exists():
        return None

    block = ReportBlock.objects.create(
        block_type=ReportBlockType.HEADING,
        content=default_content_for_block_type(ReportBlockType.HEADING),
        title_level=0,
    )
    return ReportNode.objects.create(
        report=report,
        block=block,
        position=Decimal("1"),
    )
