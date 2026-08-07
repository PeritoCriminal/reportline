# reportline/institution_ic_sp/forensic_report/services/scene_location_table.py
"""
Montagem da tabela de localização com QR code no laudo pericial.

Gera tabela 2×1 no mesmo formato persistido pelo editor (colunas redimensionáveis,
imagem embutida na célula e texto com quebras ``<br>`` equivalentes a Shift+Enter).
"""

from __future__ import annotations

from html import escape

from institution_ic_sp.forensic_report.common.services.location_maps_qr import (
    google_maps_search_url,
    location_qualifies_for_maps_qr,
    maps_qr_png_bytes,
)
from institution_ic_sp.forensic_report.common.services.scene_location import SceneLocationData
from reports.models import Report
from reports.services.report_image_upload import (
    build_image_block_content,
    store_report_image_from_bytes,
)
from reports.services.report_table_column_widths import normalize_column_widths

# Largura base do QR em pixels antes do fator de redução na geração.
_LOCATION_QR_BASE_PIXEL_SIZE = 128

# Largura do QR gerado (20% menor que a base).
LOCATION_QR_PIXEL_SIZE = round(_LOCATION_QR_BASE_PIXEL_SIZE * 0.8)

# Largura útil de referência do corpo do laudo (14 cm @ 96 DPI), para percentual da coluna.
TABLE_BODY_REFERENCE_WIDTH_PX = 529

# Folga horizontal na célula do QR e entre as colunas (evita conteúdo encostado).
QR_CELL_HORIZONTAL_PADDING_PX = 12
QR_COLUMN_GAP_PX = 16

MAPS_LINK_LABEL = "Local do exame no Google Maps"


def _column_widths_for_qr_image(qr_width_px: int) -> list[int]:
    """
    Calcula percentuais de coluna com a esquerda ajustada ao QR e o restante ao texto.

    Inclui padding interno da célula do QR e folga antes da coluna de texto.
    """
    horizontal_margin = (QR_CELL_HORIZONTAL_PADDING_PX * 2) + QR_COLUMN_GAP_PX
    left_column_px = qr_width_px + horizontal_margin
    qr_share = round(left_column_px / TABLE_BODY_REFERENCE_WIDTH_PX * 100)
    qr_share = max(15, min(38, qr_share))
    return normalize_column_widths([qr_share, 100 - qr_share], 2)


def _build_location_text_html(location: SceneLocationData, maps_url: str) -> str:
    """
    Monta HTML da coluna direita: rótulo, valor e link inline (como no editor).

    Usa ``<br>`` entre linhas — equivalente a Shift+Enter na célula editável.
    """
    label = escape(location.location_label)
    value = escape(location.location_value)
    safe_url = escape(maps_url, quote=True)
    link_text = escape(MAPS_LINK_LABEL)
    return (
        f"<strong>{label}</strong>"
        f"<br>{value}"
        f'<br><a href="{safe_url}">{link_text}</a>'
    )


def _build_qr_image_cell(report: Report, maps_url: str, maps_query: str) -> dict | None:
    """Persiste PNG do QR e retorna célula de imagem ou ``None`` quando indisponível."""
    if not location_qualifies_for_maps_qr(maps_query):
        return None

    png_bytes = maps_qr_png_bytes(maps_url, pixel_size=LOCATION_QR_PIXEL_SIZE)
    if not png_bytes:
        return None

    report_image = store_report_image_from_bytes(
        report,
        png_bytes,
        filename="qrcode-localizacao.png",
    )
    image_content = build_image_block_content(report_image)
    width = int(image_content["width"])
    height = int(image_content["height"])
    return {
        "type": "image",
        "alt": "QR code para localização no Google Maps",
        "file": image_content["file"],
        "image_id": image_content["image_id"],
        "width": width,
        "height": height,
        "align": "center",
    }


def build_scene_location_table_content(
    report: Report,
    location: SceneLocationData,
) -> dict | None:
    """
    Monta conteúdo JSON de tabela 2×1: QR (esquerda) e endereço com link (direita).

    Retorna ``None`` quando não há localização informada.
    """
    if not location.is_present:
        return None

    maps_url = google_maps_search_url(location.maps_query)
    text_html = _build_location_text_html(location, maps_url)
    text_cell = {"type": "text", "text": text_html, "align": "left"}

    qr_cell = _build_qr_image_cell(report, maps_url, location.maps_query)
    if qr_cell is None:
        qr_cell = {"type": "text", "text": "", "align": "center"}
        column_widths = normalize_column_widths([30, 70], 2)
    else:
        column_widths = _column_widths_for_qr_image(int(qr_cell["width"]))

    return {
        "headers": [],
        "rows": [[qr_cell, text_cell]],
        "show_borders": False,
        "show_header": False,
        "column_widths": column_widths,
        "display_width": 100,
    }
