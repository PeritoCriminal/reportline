# reportline/reports/services/report_user_page_layout.py
"""
Preferências de cabeçalho e rodapé por usuário.

Persiste layouts pessoais e institucionais separadamente e reaplica
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


def _stored_bands_from_layout(page_layout: dict[str, Any] | None) -> dict[str, Any]:
    """Extrai apenas cabeçalho e rodapé para persistência no perfil do usuário."""
    normalized = normalize_page_layout(page_layout)
    return {
        "header": deepcopy(normalized["header"]),
        "footer": deepcopy(normalized["footer"]),
    }


def _layout_has_enabled_bands(page_layout: dict[str, Any] | None) -> bool:
    normalized = normalize_page_layout(page_layout)
    return bool(
        normalized["header"].get("enabled") or normalized["footer"].get("enabled")
    )


def sync_user_page_layout_preferences(
    user: AbstractBaseUser,
    page_layout: dict[str, Any] | None,
) -> None:
    """Atualiza cabeçalho e rodapé padrão do usuário a partir do laudo editado."""
    config = get_or_create_user_config(user)
    stored_bands = _stored_bands_from_layout(page_layout)

    if is_forensic_report_layout(page_layout):
        config.institutional_page_layout = stored_bands
        config.save(update_fields=["institutional_page_layout", "updated_at"])
        return

    config.personal_page_layout = stored_bands
    config.save(update_fields=["personal_page_layout", "updated_at"])


def apply_user_page_layout_to_report(
    report: Report,
    user: AbstractBaseUser,
) -> Report:
    """Copia cabeçalho e rodapé pessoais salvos nas preferências do usuário para o laudo."""
    config = get_or_create_user_config(user)
    if not config.personal_page_layout:
        return report

    normalized = normalize_page_layout(config.personal_page_layout)
    if not _layout_has_enabled_bands(normalized):
        return report

    report.page_layout = clone_page_layout_for_report(normalized, report)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def _logo_cell_has_image(cell: dict[str, Any] | None) -> bool:
    """Indica se a célula de logo referencia uma imagem persistida."""
    if not isinstance(cell, dict) or cell.get("type") != "logo":
        return False
    return bool(cell.get("image_id") and cell.get("file"))


def _merge_band_preserving_fresh_logos(
    user_band: dict[str, Any],
    fresh_band: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Mantém preferências do usuário, preservando emblemas do layout fresco.

    Preferências antigas frequentemente guardam células de logo vazias; sem
    esta preservação, cada laudo novo perderia os emblemas institucionais
    recém-copiados.
    """
    merged_band = deepcopy(user_band)
    if not isinstance(fresh_band, dict):
        return merged_band

    fresh_cells = fresh_band.get("cells", [])
    merged_cells = [dict(cell) for cell in merged_band.get("cells", [])]

    for index, cell in enumerate(merged_cells):
        if _logo_cell_has_image(cell):
            continue
        if index >= len(fresh_cells):
            continue
        fresh_cell = fresh_cells[index]
        if not _logo_cell_has_image(fresh_cell):
            continue
        merged_cells[index] = deepcopy(fresh_cell)

    merged_band["cells"] = merged_cells
    return merged_band


def merge_institutional_layout_with_user_preferences(
    report: Report,
    user: AbstractBaseUser,
    fresh_layout: dict[str, Any],
) -> dict[str, Any]:
    """
    Aplica preferências institucionais salvas sobre layout recém-gerado.

    Preserva ``reportline_meta`` (incluindo snapshot oficial) do layout
    institucional fresco, permitindo restauração sem afetar relatórios pessoais.
    Emblemas do layout fresco prevalecem quando as preferências os omitem.
    """
    config = get_or_create_user_config(user)
    if not config.institutional_page_layout:
        return fresh_layout

    normalized = normalize_page_layout(config.institutional_page_layout)
    if not _layout_has_enabled_bands(normalized):
        return fresh_layout

    user_bands = clone_page_layout_for_report(normalized, report)
    merged = deepcopy(fresh_layout)
    merged["header"] = _merge_band_preserving_fresh_logos(
        user_bands["header"],
        fresh_layout.get("header"),
    )
    merged["footer"] = _merge_band_preserving_fresh_logos(
        user_bands["footer"],
        fresh_layout.get("footer"),
    )
    return merged


def user_page_layout_or_default(user: AbstractBaseUser) -> dict[str, Any]:
    """Retorna layout de faixas pessoais padrão do usuário normalizado."""
    config = get_or_create_user_config(user)
    if not config.personal_page_layout:
        return default_page_layout()
    return normalize_page_layout(config.personal_page_layout)
