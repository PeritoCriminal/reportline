# reportline/institution_ic_sp/forensic_report/common/services/case_metadata.py
"""
Metadados de caso inferidos ou informados no intake de laudo pericial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from institution_ic_sp.forensic_report.common.services.datetime_display import (
    format_designation_date,
    format_forensic_datetime,
)
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_UNKNOWN,
    normalize_exam_category,
)

UPPERCASE_TEXT_FIELDS = frozenset(
    {
        "report_number",
        "attendance_protocol",
        "occurrence_report",
        "police_inquiry",
    }
)

# Campos de nomes próprios / unidades com capitalização normativa do português.
PROPER_NAME_TEXT_FIELDS = frozenset(
    {
        "requesting_authority",
        "police_district",
        "examiner",
        "photography",
        "scanning_3d",
        "sketch",
    }
)

# Preposições, artigos e conjunções que permanecem em minúsculas no meio do nome.
PORTUGUESE_NAME_PARTICLES = frozenset(
    {
        "a",
        "as",
        "à",
        "às",
        "ao",
        "aos",
        "o",
        "os",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "em",
        "na",
        "no",
        "nas",
        "nos",
        "para",
        "por",
        "com",
        "sem",
        "sob",
        "sobre",
        "entre",
    }
)


def _capitalize_token(token: str) -> str:
    """Capitaliza a primeira letra alfabética e deixa o restante em minúsculas."""
    chars = list(token)
    found_letter = False
    for index, char in enumerate(chars):
        if not char.isalpha():
            continue
        chars[index] = char.upper() if not found_letter else char.lower()
        found_letter = True
    return "".join(chars)


def _format_portuguese_name_word(word: str, *, is_first: bool, force_title: bool) -> str:
    """Aplica capitalização normativa a um token (suporta hífens)."""
    if "-" in word:
        parts = word.split("-")
        return "-".join(
            _format_portuguese_name_word(
                part,
                is_first=is_first and index == 0,
                force_title=force_title,
            )
            for index, part in enumerate(parts)
        )

    lowered = word.lower()
    if not is_first and lowered in PORTUGUESE_NAME_PARTICLES:
        return lowered

    letters = [char for char in word if char.isalpha()]
    if (
        not force_title
        and letters
        and all(char.isupper() for char in letters)
        and 2 <= len(letters) <= 5
    ):
        # Preserve siglas em entradas mistas (ex.: "1º DP", "DEIC").
        return word

    return _capitalize_token(word)


def format_portuguese_proper_name(value: str) -> str:
    """
    Capitalização normativa de nomes próprios em português.

    Primeira letra de cada palavra em maiúscula; preposições/artigos/conjunções
    em minúsculas no meio do nome. Entradas inteiramente em maiúsculas são
    reescritas; siglas curtas são preservadas quando isoladas ou em entradas mistas.
    """
    cleaned = value.strip()
    if not cleaned:
        return cleaned

    letters = [char for char in cleaned if char.isalpha()]
    # Sigla isolada (sem espaços): manter caixa original.
    if " " not in cleaned and letters and all(char.isupper() for char in letters):
        if 2 <= len(letters) <= 5:
            return cleaned

    force_title = bool(letters) and all(char.isupper() for char in letters)

    words = cleaned.split()
    return " ".join(
        _format_portuguese_name_word(word, is_first=index == 0, force_title=force_title)
        for index, word in enumerate(words)
    )


def normalize_text_field(name: str, value: str) -> str:
    """
    Normaliza campo textual conforme regras de caixa do intake.

    Identificadores administrativos ficam em maiúsculas; nomes próprios
    recebem capitalização normativa do português; demais textos livres
    permanecem na caixa informada pelo perito.
    """
    cleaned = value.strip()
    if name in UPPERCASE_TEXT_FIELDS:
        return cleaned.upper()
    if name in PROPER_NAME_TEXT_FIELDS:
        return format_portuguese_proper_name(cleaned)
    return cleaned


def format_report_number_display(number: str) -> str:
    """Formata a parte numérica do laudo com separador de milhar '.' para exibição."""
    cleaned = number.strip()
    if not cleaned:
        return cleaned
    match = re.match(r"^(\d+)(.*)$", cleaned)
    if not match:
        return cleaned
    digits, suffix = match.group(1), match.group(2)
    formatted_parts: list[str] = []
    while digits:
        formatted_parts.insert(0, digits[-3:])
        digits = digits[:-3]
    return ".".join(formatted_parts) + suffix


def normalize_case_metadata(metadata: CaseMetadata) -> CaseMetadata:
    """Aplica regras de caixa alta/baixa aos campos textuais do intake."""
    normalized: dict[str, object] = {}
    for field_name in metadata.__dataclass_fields__:
        value = getattr(metadata, field_name)
        if isinstance(value, str):
            normalized[field_name] = normalize_text_field(field_name, value)
        else:
            normalized[field_name] = value
    return CaseMetadata(**normalized)


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
    exam_category: str = EXAM_CATEGORY_UNKNOWN
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
        number = format_report_number_display(self.report_number.strip())
        year = self.report_year or 0
        if number and year:
            return f"LAUDO PERICIAL Nº {number}/{year}"
        if number:
            return f"LAUDO PERICIAL Nº {number}"
        return "LAUDO PERICIAL"

    @property
    def header_report_number_text(self) -> str:
        """Texto do número do laudo exibido abaixo do cabeçalho institucional."""
        number = format_report_number_display(self.report_number.strip())
        year = self.report_year or 0
        if number and year:
            return f"Laudo pericial nº {number}/{year}"
        if number:
            return f"Laudo pericial nº {number}"
        return "Laudo pericial"

    @property
    def list_title(self) -> str:
        """Título curto usado na listagem de relatórios."""
        number = format_report_number_display(self.report_number.strip())
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
