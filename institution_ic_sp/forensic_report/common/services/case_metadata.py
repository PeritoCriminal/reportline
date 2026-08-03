"""
Metadados de caso inferidos ou informados no intake de laudo pericial.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CaseMetadata:
    """
    Dados administrativos do laudo reunidos na etapa comum de intake.

    Campos opcionais permanecem vazios quando a extração ou o perito
    não os informarem; o builder omite itens ausentes nas listas.
    """

    report_number: str = ""
    report_year: int = 0
    service_protocol: str = ""
    requester: str = ""
    case_type: str = ""
    bulletin_number: str = ""
    exam_objective: str = ""
    supplementary_prompt: str = ""
    uploaded_file_names: list[str] = field(default_factory=list)

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

    def requisition_list_items(self) -> list[str]:
        """Itens para a seção Dados da Requisição."""
        items: list[str] = []
        if self.requester.strip():
            items.append(f"Solicitante: {self.requester.strip()}")
        if self.case_type.strip():
            items.append(f"Tipo de caso: {self.case_type.strip()}")
        if self.bulletin_number.strip():
            items.append(f"Boletim de ocorrência nº: {self.bulletin_number.strip()}")
        return items

    def attendance_list_items(self, *, unit_label: str, city_label: str) -> list[str]:
        """Itens para a seção Dados do Atendimento."""
        items: list[str] = []
        if self.service_protocol.strip():
            items.append(f"Protocolo de atendimento: {self.service_protocol.strip()}")
        if unit_label.strip():
            items.append(f"Unidade pericial: {unit_label.strip()}")
        if city_label.strip():
            items.append(f"Município: {city_label.strip()}")
        return items
