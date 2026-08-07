# reportline/institution_ic_sp/forensic_report/common/services/datetime_display.py
"""
Formatação de datas para laudos periciais do IC-SP.
"""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

MONTHS_ABBR_PT = (
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez",
)

MONTHS_FULL_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def _to_local_datetime(value: datetime) -> datetime:
    """Normaliza datetime consciente para fuso local."""
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


def format_forensic_datetime(value: datetime | None) -> str:
    """
    Formata data e hora para listas do laudo.

    Exemplo: ``03 de ago de 2026, às 14h30``.
    """
    if value is None:
        return ""
    local = _to_local_datetime(value)
    month = MONTHS_ABBR_PT[local.month - 1]
    return f"{local.day:02d} de {month} de {local.year}, às {local.hour:02d}h{local.minute:02d}"


def format_designation_date(value: date | None) -> str:
    """
    Formata data de designação para o preâmbulo.

    Exemplo: ``3 de agosto de 2026``.
    """
    if value is None:
        return ""
    month = MONTHS_FULL_PT[value.month - 1]
    return f"{value.day} de {month} de {value.year}"
