# reportline/institution_ic_sp/tests/test_forensic_datetime_display.py
"""
Testes de formatação de datas para laudos periciais.
"""

from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.datetime_display import (
    format_designation_date,
    format_forensic_datetime,
)


class ForensicDatetimeDisplayTests(TestCase):
    """Testes de exibição de datas no laudo pericial."""

    def test_format_forensic_datetime_uses_portuguese_pattern(self):
        """Garante formato abreviado com hora para listas do laudo."""
        value = timezone.make_aware(datetime(2026, 8, 3, 14, 30))
        formatted = format_forensic_datetime(value)
        self.assertEqual(formatted, "03 de ago de 2026, às 14h30")

    def test_format_designation_date_uses_full_month(self):
        """Garante formato longo de data para o preâmbulo."""
        formatted = format_designation_date(date(2026, 8, 3))
        self.assertEqual(formatted, "3 de agosto de 2026")

    def test_empty_values_return_blank_string(self):
        """Garante string vazia quando datetime ou date são nulos."""
        self.assertEqual(format_forensic_datetime(None), "")
        self.assertEqual(format_designation_date(None), "")
