# reportline/institution_ic_sp/forensic_report/common/services/location_maps_qr.py
"""
URL do Google Maps e geração de QR code para localização pericial.

Adaptado do módulo homólogo do pith (`forensic_reports/location_maps_qr.py`),
sem dependência de HTML estático — retorna bytes PNG ou data URI para uso
no editor ReportLine.
"""

from __future__ import annotations

import base64
import logging
import re
import unicodedata
from io import BytesIO
from urllib.parse import quote

logger = logging.getLogger(__name__)

_CEP_RE = re.compile(r"\b\d{5}-?\d{3}\b")
_COORD_PAIR_RE = re.compile(
    r"(?<![\d.,-])"
    r"(-?\d{1,2}(?:\.\d+)?)\s*[,;]\s*"
    r"(-?\d{1,3}(?:\.\d+)?)"
    r"(?!\d)",
)
_ADDRESS_HINT_RE = re.compile(
    r"(?i)\b("
    r"rua|r\.|avenida|av\.|av\b|alameda|al\.|travessa|tv\.|praca|pc\.|"
    r"rodovia|estrada|est\.|loteamento|condominio|quadra|qd\.|conjunto|cj\.|"
    r"chacara|fazenda|sitio|vila|cep\b|"
    r"logradouro|endereco|residencia|edificio|predio|galpao|"
    r"br[- ]?\d{1,3}\b|"
    r"street|st\.|avenue|ave\.|road|rd\.|lane|boulevard|blvd\.|route|drive|dr\."
    r")\b",
)
_ADDRESS_EXTRA_RE = re.compile(
    r"(?iu)\b("
    r"n[º°]|n[oó]\.?|num\.?|n[uú]mero|apto\.?|ap\.|sala|andar|blocos?|"
    r"km\s*\d|lotes?|setores?"
    r")\b",
)


def _normalize_for_hints(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").strip())
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()


def _has_plausible_coord_pair(text: str) -> bool:
    for match in _COORD_PAIR_RE.finditer(text):
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
        except ValueError:
            continue
        if abs(lat) <= 90 and abs(lng) <= 180:
            return True
    return False


def location_qualifies_for_maps_qr(text: str) -> bool:
    """
    Heurística: texto parece endereço, coordenadas ou local resolvível no Maps.

    Não chama APIs externas. Quando retorna falso, o laudo pode exibir só o texto.
    """
    raw = (text or "").strip()
    if len(raw) < 8:
        return False
    if _CEP_RE.search(raw):
        return True
    if _has_plausible_coord_pair(raw):
        return True
    norm = _normalize_for_hints(raw)
    if _ADDRESS_HINT_RE.search(norm):
        return True
    if _ADDRESS_EXTRA_RE.search(raw) or _ADDRESS_EXTRA_RE.search(norm):
        return True
    if "," in raw and len(raw) >= 14 and any(ch.isdigit() for ch in raw):
        return True
    return False


def google_maps_search_url(query: str) -> str:
    """Monta URL de busca no Google Maps para endereço ou coordenadas."""
    cleaned = (query or "").strip()
    if not cleaned:
        return "https://www.google.com/maps"
    return f"https://www.google.com/maps/search/?api=1&query={quote(cleaned, safe='')}"


def maps_qr_png_bytes(url: str, *, pixel_size: int = 240) -> bytes | None:
    """
    Gera PNG do QR code apontando para ``url``.

    Retorna ``None`` quando a biblioteca ``qrcode`` não estiver disponível
    ou a codificação falhar.
    """
    payload = (url or "").strip()
    if not payload:
        return None
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError:
        logger.error(
            "Pacote qrcode não instalado; QR de localização desabilitado."
        )
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    try:
        from PIL import Image

        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img = img.resize((pixel_size, pixel_size), Image.Resampling.NEAREST)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.exception("Falha ao gerar PNG do QR code de localização.")
        return None


def maps_qr_png_data_uri(url: str, *, pixel_size: int = 240) -> str | None:
    """Converte PNG do QR em data URI para uso pontual em HTML."""
    png_bytes = maps_qr_png_bytes(url, pixel_size=pixel_size)
    if not png_bytes:
        return None
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"
