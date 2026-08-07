# reportline/institution_ic_sp/forensic_report/common/services/scene_location.py
"""
Normalização e montagem de localização para exame de local patrimonial.
"""

from __future__ import annotations

from dataclasses import dataclass

LOCATION_KIND_ADDRESS = "address"
LOCATION_KIND_COORDINATES = "coordinates"


@dataclass
class SceneLocationData:
    """Local informado pelo perito para QR code e tabela de localização."""

    kind: str = ""
    address: str = ""
    latitude: str = ""
    longitude: str = ""

    @property
    def is_present(self) -> bool:
        """Indica se há endereço ou coordenadas válidas."""
        if self.kind == LOCATION_KIND_ADDRESS:
            return bool(self.address.strip())
        if self.kind == LOCATION_KIND_COORDINATES:
            return bool(self.latitude.strip() and self.longitude.strip())
        return False

    @property
    def maps_query(self) -> str:
        """Texto usado na URL do Google Maps."""
        if self.kind == LOCATION_KIND_COORDINATES:
            return f"{self.latitude.strip()}, {self.longitude.strip()}"
        return self.address.strip()

    @property
    def location_label(self) -> str:
        """Rótulo exibido na célula de texto da tabela de localização."""
        if self.kind == LOCATION_KIND_COORDINATES:
            return "Coordenadas:"
        return "Endereço:"

    @property
    def location_value(self) -> str:
        """Valor (endereço ou par lat/long) exibido abaixo do rótulo."""
        return self.maps_query if self.is_present else ""

    @property
    def display_text(self) -> str:
        """Texto legado para exibição resumida da localização."""
        if not self.is_present:
            return ""
        return f"{self.location_label} {self.location_value}".strip()


def normalize_scene_location(raw: dict | None) -> SceneLocationData:
    """Converte payload JSON da continuação em ``SceneLocationData``."""
    if not isinstance(raw, dict):
        return SceneLocationData()
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in {LOCATION_KIND_ADDRESS, LOCATION_KIND_COORDINATES}:
        return SceneLocationData()
    return SceneLocationData(
        kind=kind,
        address=str(raw.get("address", "")).strip(),
        latitude=str(raw.get("latitude", "")).strip(),
        longitude=str(raw.get("longitude", "")).strip(),
    )


def scene_location_from_bootstrap(page_layout: dict | None) -> SceneLocationData:
    """Lê localização persistida em ``scene_characteristics.location``."""
    from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
        scene_characteristics_from_bootstrap,
    )

    characteristics = scene_characteristics_from_bootstrap(page_layout)
    raw_location = characteristics.get("location")
    if not isinstance(raw_location, dict):
        return SceneLocationData()
    return normalize_scene_location(raw_location)


def exam_location_from_dossier(report) -> SceneLocationData:
    """
    Monta localização a partir de ``extensions`` da fase ``initial_data``.

    Usa ``exam_location_address`` ou par ``exam_location_latitude`` /
    ``exam_location_longitude`` quando documentados na extração administrativa.
    """
    from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
        initial_data_extensions_for_report,
    )

    extensions = initial_data_extensions_for_report(report)
    address = str(extensions.get("exam_location_address", "")).strip()
    if address:
        return SceneLocationData(kind=LOCATION_KIND_ADDRESS, address=address)

    latitude = str(extensions.get("exam_location_latitude", "")).strip()
    longitude = str(extensions.get("exam_location_longitude", "")).strip()
    if latitude and longitude:
        return SceneLocationData(
            kind=LOCATION_KIND_COORDINATES,
            latitude=latitude,
            longitude=longitude,
        )
    return SceneLocationData()


def resolve_scene_location(*, manual: SceneLocationData, report) -> SceneLocationData:
    """Prioriza local informado pelo perito; complementa com endereço do dossiê."""
    if manual.is_present:
        return manual
    return exam_location_from_dossier(report)


def scene_location_for_report(report) -> SceneLocationData:
    """Retorna localização do bootstrap ou, se ausente, inferida do dossiê."""
    location = scene_location_from_bootstrap(report.page_layout)
    if location.is_present:
        return location
    return exam_location_from_dossier(report)


def scene_location_to_payload(location: SceneLocationData) -> dict[str, str]:
    """Serializa localização para JSON de API ou bootstrap."""
    return {
        "kind": location.kind,
        "address": location.address,
        "latitude": location.latitude,
        "longitude": location.longitude,
    }
