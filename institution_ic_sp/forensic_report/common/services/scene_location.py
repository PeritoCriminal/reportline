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
