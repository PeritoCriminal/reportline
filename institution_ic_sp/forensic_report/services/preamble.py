# reportline/institution_ic_sp/forensic_report/services/preamble.py
"""
Texto de preâmbulo do laudo pericial genérico e concordância de gênero.
"""

from __future__ import annotations

import re

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.datetime_display import (
    format_designation_date,
)
from institution_ic_sp.forensic_report.services.institution_page_layout import (
    get_examiner_assignment_labels,
)
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP, GenderCalling


def infer_requesting_authority_gender(raw_authority: str) -> str | None:
    """
    Infere tratamento masculino/feminino pelo prefixo Dr./Dra. na autoridade.

    Retorna ``None`` quando o prefixo estiver ausente (texto neutro no preâmbulo).
    """
    value = (raw_authority or "").strip()
    if re.match(r"^dra\.", value, re.IGNORECASE):
        return GenderCalling.FEMALE
    if re.match(r"^dr\.", value, re.IGNORECASE):
        return GenderCalling.MALE
    return None


def strip_leading_dr_prefix(name: str) -> str:
    """Remove prefixo Dr./Dra. para reaplicar honorífico coerente."""
    cleaned = (name or "").strip()
    return re.sub(r"^dra?\.\s*", "", cleaned, flags=re.IGNORECASE).strip()


def authority_with_honorific(
    raw_authority: str,
    *,
    requesting_authority_gender: str | None = None,
) -> str:
    """Formata autoridade requisitante com Dr./Dra. quando o gênero é conhecido."""
    raw = (raw_authority or "").strip()
    body = strip_leading_dr_prefix(raw)
    if not body:
        return ""

    gender = requesting_authority_gender
    if gender is None:
        gender = infer_requesting_authority_gender(raw)

    if gender == GenderCalling.FEMALE:
        return f"Dra. {body}"
    if gender == GenderCalling.MALE:
        return f"Dr. {body}"
    return body


def requisition_authority_clause(*, requesting_authority_gender: str | None) -> str:
    """Trecho delegado do preâmbulo (pelo/pela, Delegado/Delegada)."""
    if requesting_authority_gender == GenderCalling.FEMALE:
        return "pela Exma. Sra. Delegada de Polícia"
    if requesting_authority_gender == GenderCalling.MALE:
        return "pelo Exmo. Sr. Delegado de Polícia"
    return "pelo(a) Exmo(a). Sr(a). Delegado(a) de Polícia"


def examiner_designation_phrase(*, calling_gender: str | None) -> str:
    """Frase de designação do perito no preâmbulo."""
    if calling_gender == GenderCalling.FEMALE:
        return "foi designada a Perita Criminal"
    return "foi designado o Perito Criminal"


def _examiner_city(examiner: ForensicExaminerSP) -> str:
    """Retorna município da lotação pericial do examinador."""
    _unit, city = get_examiner_assignment_labels(examiner)
    return city.strip()


def build_preamble_paragraph(
    metadata: CaseMetadata,
    *,
    examiner: ForensicExaminerSP,
    institution: Institution | None = None,
) -> str:
    """
    Monta preâmbulo legal conforme metadados, perfil pericial e instituição.

    Omite trechos dependentes de campos ausentes (autoridade, data, diretor).
    """
    institution = institution or Institution.objects.first()
    date_text = format_designation_date(metadata.designation_date)
    city = _examiner_city(examiner)
    team, _city = get_examiner_assignment_labels(examiner)
    director = (examiner.director_display or "").strip()
    if not director and institution is not None:
        director = (institution.director_display or "").strip()

    examiner_name = (metadata.examiner or examiner.display_name or "").strip()
    designation_phrase = examiner_designation_phrase(
        calling_gender=examiner.calling_gender or None,
    )

    raw_authority = (metadata.requesting_authority or "").strip()
    authority_gender = infer_requesting_authority_gender(raw_authority)
    authority = authority_with_honorific(
        raw_authority,
        requesting_authority_gender=authority_gender,
    )

    institution_name = institution.name if institution else "Instituto de Criminalística"
    parent_org = (
        institution.parent_organization
        if institution
        else "Superintendência da Polícia Técnico-Científica"
    )

    opening = ""
    if date_text:
        opening = f"Aos {date_text}, "
    opening += f"na cidade de {city or '—'}, no {institution_name} da {parent_org}"
    if team:
        opening += f", no {team}"

    body = (
        f"{opening}, em conformidade com o disposto no artigo 178 do Decreto-Lei "
        f"nº 3.689, de 3 de outubro de 1941, pelo Perito Criminal Diretor deste "
        f"Instituto de Criminalística"
    )
    if director:
        body += f", {director}"
    body += f", {designation_phrase}"
    if examiner_name:
        body += f" {examiner_name}"
    body += " para proceder ao exame pericial"

    if authority:
        clause = requisition_authority_clause(
            requesting_authority_gender=authority_gender,
        )
        body += f", em atendimento à requisição expedida {clause} {authority}"

    body += "."
    return " ".join(body.split())
