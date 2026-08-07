# reportline/institution_ic_sp/forensic_report/services/trace_report_image_nodes.py
"""
Inserção de blocos nativos de imagem e legenda na seção de vestígios.
"""

from __future__ import annotations

from reports.models import ReportNode
from reports.services.report_image_nodes import insert_report_image_nodes


def insert_trace_report_image_nodes(ctx, report_images: list[dict[str, str]]) -> list[ReportNode]:
    """
    Insere nós IMAGE seguidos de parágrafo legenda após o parágrafo do vestígio.

    ``report_images`` deve conter ``image_id`` e ``caption`` já ajustados pela IA.
    """
    from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
        _insert_scene_report_node,
    )

    return insert_report_image_nodes(
        ctx,
        report_images,
        insert_node=_insert_scene_report_node,
    )
