"""
Metadados de caso inferidos ou informados no intake de laudo pericial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from institution_ic_sp.forensic_report.common.services.datetime_display import (
    format_designation_date,
    format_forensic_datetime,
)


@dataclass
class CaseMetadata:
    """
    Dados administrativos do laudo reunidos na etapa comum de intake.

    Campos opcionais permanecem vazios quando a extração ou o perito
    não os informarem; o builder omite itens ausentes nas listas.
    """

    report_number: str = ""
    report_year: int = 0
    designation_date: date | None = None
    exam_objective: str = ""
    supplementary_prompt: str = ""
    requesting_authority: str = ""
    police_district: str = ""
    occurrence_report: str = ""
    police_inquiry: str = ""
    occurrence_at: datetime | None = None
    requisition_at: datetime | None = None
    attendance_protocol: str = ""
    examiner: str = ""
    examination_at: datetime | None = None
    photography: str = ""
    scanning_3d: str = ""
    sketch: str = ""

    @property
    def main_title_text(self) -> str:
        """Texto do título principal no formato institucional."""
        number = self.report_number.strip()
        year = self.report_year or 0
        if number and year:
            return f"LAUDO PERICIAL Nº {number}/{year}"
        if number:
            return f"LAUDO PERICIAL Nº {number}"
        return "LAUDO PERICIAL"

    @property
    def list_title(self) -> str:
        """Título curto usado na listagem de relatórios."""
        number = self.report_number.strip()
        year = self.report_year or 0
        if number and year:
            return f"Laudo pericial {number}/{year}"
        if number:
            return f"Laudo pericial {number}"
        return "Laudo pericial"

    def _labeled_items(self, pairs: list[tuple[str, str]]) -> list[str]:
        """Monta itens de lista omitindo pares com valor vazio."""
        items: list[str] = []
        for label, value in pairs:
            cleaned = value.strip() if isinstance(value, str) else value
            if cleaned:
                items.append(f"{label}: {cleaned}")
        return items

    def requisition_list_items(self) -> list[str]:
        """Itens para a seção Dados da Requisição."""
        return self._labeled_items(
            [
                ("Autoridade requisitante", self.requesting_authority),
                ("Distrito policial / Delegacia", self.police_district),
                ("Boletim de ocorrência", self.occurrence_report),
                ("Inquérito policial", self.police_inquiry),
                (
                    "Data e hora da ocorrência",
                    format_forensic_datetime(self.occurrence_at),
                ),
                (
                    "Data e hora da requisição",
                    format_forensic_datetime(self.requisition_at),
                ),
            ]
        )

    def attendance_list_items(self) -> list[str]:
        """Itens para a seção Dados do Atendimento."""
        return self._labeled_items(
            [
                ("Número do protocolo", self.attendance_protocol),
                ("Perito", self.examiner),
                (
                    "Data e hora do exame",
                    format_forensic_datetime(self.examination_at),
                ),
                ("Fotógrafo", self.photography),
                ("Escaneamento 3D", self.scanning_3d),
                ("Croqui", self.sketch),
            ]
        )
