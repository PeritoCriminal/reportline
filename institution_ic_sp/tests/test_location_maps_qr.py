# reportline/institution_ic_sp/tests/test_location_maps_qr.py
"""
Testes de QR code e URL do Google Maps para localização pericial.
"""

from django.test import SimpleTestCase

from institution_ic_sp.forensic_report.common.services.location_maps_qr import (
    google_maps_search_url,
    location_qualifies_for_maps_qr,
    maps_qr_png_bytes,
)


class LocationMapsQrTests(SimpleTestCase):
    """Testes do serviço de QR code adaptado do pith."""

    def test_google_maps_search_url_encodes_address(self):
        """Garante montagem da URL de busca no Google Maps."""
        url = google_maps_search_url("Rua XV de Novembro, 100 — Curitiba")
        self.assertIn("google.com/maps/search/", url)
        self.assertIn("query=", url)

    def test_location_qualifies_for_coordinates(self):
        """Garante heurística positiva para par de coordenadas."""
        self.assertTrue(location_qualifies_for_maps_qr("-23.5505, -46.6333"))

    def test_maps_qr_png_bytes_returns_png(self):
        """Garante geração de bytes PNG para URL do Maps."""
        png = maps_qr_png_bytes(google_maps_search_url("Av. Paulista, 1000"))
        self.assertIsNotNone(png)
        assert png is not None
        self.assertTrue(png.startswith(b"\x89PNG"))
