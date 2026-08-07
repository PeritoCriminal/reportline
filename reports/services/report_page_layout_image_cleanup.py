# reportline/reports/services/report_page_layout_image_cleanup.py
"""
Limpeza de imagens referenciadas no layout de página (cabeçalho e rodapé).
"""

from __future__ import annotations

from typing import Any

from reports.services.report_image_upload import delete_report_image
from reports.services.report_kind import institutional_page_layout_snapshot
from reports.services.report_page_layout import normalize_page_layout


def collect_image_ids_from_band_layout(band_layout: dict[str, Any] | None) -> set[str]:
    """Retorna IDs de ``ReportImage`` referenciados nas células de logo da faixa."""
    if not band_layout or not band_layout.get("enabled"):
        return set()

    image_ids: set[str] = set()
    for cell in band_layout.get("cells", []):
        if cell.get("type") != "logo":
            continue
        image_id = cell.get("image_id")
        if image_id:
            image_ids.add(str(image_id))
    return image_ids


def collect_image_ids_from_page_layout(page_layout: dict[str, Any] | None) -> set[str]:
    """Retorna IDs de imagem referenciados no cabeçalho e rodapé do relatório."""
    normalized = normalize_page_layout(page_layout)
    ids = collect_image_ids_from_band_layout(normalized.get("header"))
    ids.update(collect_image_ids_from_band_layout(normalized.get("footer")))
    return ids


def collect_snapshot_protected_image_ids(page_layout: dict[str, Any] | None) -> set[str]:
    """Retorna IDs de imagem preservados no snapshot institucional do laudo."""
    snapshot = institutional_page_layout_snapshot(page_layout)
    if not snapshot:
        return set()

    protected: set[str] = set()
    protected.update(collect_image_ids_from_band_layout(snapshot.get("header")))
    protected.update(collect_image_ids_from_band_layout(snapshot.get("footer")))
    return protected


def delete_removed_page_layout_images(
    old_layout: dict[str, Any] | None,
    new_layout: dict[str, Any] | None,
) -> None:
    """Remove imagens que deixaram de ser referenciadas após alteração do layout."""
    old_ids = collect_image_ids_from_page_layout(old_layout)
    new_ids = collect_image_ids_from_page_layout(new_layout)
    protected = collect_snapshot_protected_image_ids(old_layout) | collect_snapshot_protected_image_ids(
        new_layout
    )
    for image_id in old_ids - new_ids:
        if image_id in protected:
            continue
        delete_report_image(image_id)
