# reportline/reports/services/report_user_page_layout.py
"""
Preferências de cabeçalho e rodapé por usuário.

Persiste o último layout de faixas editado pelo usuário e reaplica
cópias em laudos novos, clonando imagens referenciadas quando necessário.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.files.base import ContentFile
from django.db import transaction

from reports.models import Report, ReportImage
from reports.services.report_page_layout import (
    default_logo_cell,
    default_page_layout,
    normalize_page_layout,
)
from reports.services.report_kind import is_forensic_report_layout
from reports.services.report_user_config import get_or_create_user_config


@transaction.atomic
def clone_report_image(source_image: ReportImage, target_report: Report) -> ReportImage:
    """Duplica arquivo de imagem persistida para outro laudo."""
    extension = (
        source_image.image.name.rsplit(".", 1)[-1].lower()
        if "." in source_image.image.name
        else "jpg"
    )
    clone = ReportImage(
        report=target_report,
        width=source_image.width,
        height=source_image.height,
        original_filename=source_image.original_filename,
    )
    clone.save()

    source_image.image.open()
    try:
        content = source_image.image.read()
    finally:
        source_image.image.close()

    clone.image.save(
        f"{clone.pk}.{extension}",
        ContentFile(content),
        save=True,
    )
    return clone


def clone_page_layout_for_report(
    source_layout: dict[str, Any] | None,
    target_report: Report,
) -> dict[str, Any]:
    """
    Copia cabeçalho e rodapé para um laudo, clonando logos referenciadas.

    Se a imagem de origem não existir mais, a célula de logo é esvaziada.
    """
    normalized = normalize_page_layout(deepcopy(source_layout))

    for band_key in ("header", "footer"):
        band = normalized[band_key]
        if not band.get("enabled"):
            continue

        cloned_cells: list[dict[str, Any]] = []
        for cell in band.get("cells", []):
            cell_copy = dict(cell)
            if cell_copy.get("type") != "logo" or not cell_copy.get("image_id"):
                cloned_cells.append(cell_copy)
                continue

            try:
                source_image = ReportImage.objects.get(pk=cell_copy["image_id"])
            except ReportImage.DoesNotExist:
                cloned_cells.append(
                    default_logo_cell(logo_slot=cell_copy.get("logo_slot", "primary"))
                )
                continue

            cloned_image = clone_report_image(source_image, target_report)
            cell_copy["image_id"] = str(cloned_image.pk)
            cell_copy["file"] = cloned_image.image.name
            if not cell_copy.get("width"):
                cell_copy["width"] = cloned_image.width
            if not cell_copy.get("height"):
                cell_copy["height"] = cloned_image.height
            cloned_cells.append(cell_copy)

        band["cells"] = cloned_cells

    return normalized


def sync_user_page_layout_preferences(
    user: AbstractBaseUser,
    page_layout: dict[str, Any] | None,
) -> None:
    """Atualiza cabeçalho e rodapé padrão do usuário a partir do laudo editado."""
    if is_forensic_report_layout(page_layout):
        return

    config = get_or_create_user_config(user)
    normalized = normalize_page_layout(page_layout)
    config.page_layout = {
        "header": deepcopy(normalized["header"]),
        "footer": deepcopy(normalized["footer"]),
    }
    config.save(update_fields=["page_layout", "updated_at"])


def apply_user_page_layout_to_report(
    report: Report,
    user: AbstractBaseUser,
) -> Report:
    """Copia cabeçalho e rodapé salvos nas preferências do usuário para o laudo."""
    config = get_or_create_user_config(user)
    if not config.page_layout:
        return report

    normalized = normalize_page_layout(config.page_layout)
    if not normalized["header"].get("enabled") and not normalized["footer"].get("enabled"):
        return report

    report.page_layout = clone_page_layout_for_report(normalized, report)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def user_page_layout_or_default(user: AbstractBaseUser) -> dict[str, Any]:
    """Retorna layout de faixas padrão do usuário normalizado."""
    config = get_or_create_user_config(user)
    if not config.page_layout:
        return default_page_layout()
    return normalize_page_layout(config.page_layout)
