"""
Restauração de cabeçalho e rodapé institucionais congelados no laudo.

Recupera faixas a partir do snapshot gravado na criação do rascunho,
sem reler ``Institution``, perito ou logos originais.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from django.core.exceptions import ValidationError

from institution_ic_sp.forensic_report.services.institution_page_layout import (
    rehydrate_institutional_header_logos,
)
from institution_ic_sp.models import Institution
from reports.models import Report
from reports.services.report_kind import (
    institutional_page_layout_snapshot,
    is_forensic_report,
)
from reports.services.report_page_layout import normalize_page_layout

InstitutionalRestoreSection = Literal["header", "footer", "both"]


def restore_institutional_page_layout(
    report: Report,
    *,
    section: InstitutionalRestoreSection = "both",
) -> dict:
    """
    Restaura cabeçalho, rodapé ou ambos a partir do snapshot institucional.

    Levanta ``ValidationError`` quando o laudo não é pericial ou não possui
    snapshot congelado.
    """
    if not is_forensic_report(report):
        raise ValidationError("Restauração institucional disponível apenas em laudos periciais.")

    snapshot = institutional_page_layout_snapshot(report.page_layout)
    if not snapshot:
        raise ValidationError(
            "Este laudo não possui cópia original do cabeçalho e rodapé institucionais."
        )

    if section not in ("header", "footer", "both"):
        raise ValidationError("Informe section como header, footer ou both.")

    old_layout = report.page_layout
    updated = normalize_page_layout(old_layout)

    if section in ("header", "both"):
        if not isinstance(snapshot.get("header"), dict):
            raise ValidationError("Cópia original do cabeçalho institucional está indisponível.")
        updated["header"] = deepcopy(snapshot["header"])

    if section in ("footer", "both"):
        if not isinstance(snapshot.get("footer"), dict):
            raise ValidationError("Cópia original do rodapé institucional está indisponível.")
        updated["footer"] = deepcopy(snapshot["footer"])

    normalized = normalize_page_layout(updated)

    if section in ("header", "both"):
        institution = Institution.objects.first()
        normalized = rehydrate_institutional_header_logos(
            report,
            normalized,
            institution=institution,
        )

    return normalized
