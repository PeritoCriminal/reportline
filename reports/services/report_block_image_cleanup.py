# reportline/reports/services/report_block_image_cleanup.py
"""
Serviço de limpeza de imagens referenciadas em blocos de relatório.
"""

from __future__ import annotations

from reports.models import ReportBlockType
from reports.services.report_image_upload import delete_report_image
from reports.services.report_table_cell_content import collect_image_ids_from_table_content


def collect_image_ids_from_block(block_type: str, content: dict | None) -> list[str]:
    """Retorna IDs de ``ReportImage`` referenciados no conteúdo do bloco."""
    if not content:
        return []

    if block_type == ReportBlockType.IMAGE:
        image_id = content.get("image_id")
        return [str(image_id)] if image_id else []

    if block_type == ReportBlockType.TABLE:
        return collect_image_ids_from_table_content(content)

    return []


def delete_block_images(block_type: str, content: dict | None) -> None:
    """Remove arquivos de imagem associados ao conteúdo do bloco."""
    for image_id in collect_image_ids_from_block(block_type, content):
        delete_report_image(image_id)


def delete_removed_block_images(
    block_type: str,
    old_content: dict | None,
    new_content: dict | None,
) -> None:
    """Remove imagens que deixaram de ser referenciadas após atualização do bloco."""
    old_ids = set(collect_image_ids_from_block(block_type, old_content))
    new_ids = set(collect_image_ids_from_block(block_type, new_content))
    for image_id in old_ids - new_ids:
        delete_report_image(image_id)
