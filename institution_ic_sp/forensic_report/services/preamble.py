"""
Texto de preâmbulo do laudo pericial genérico.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.datetime_display import (
    format_designation_date,
)
from institution_ic_sp.forensic_report.services.institution_page_layout import (
    get_examiner_assignment_labels,
)
from institution_ic_sp.forensic_report.services.preamble_gender import (
    authority_with_honorific,
    examiner_designation_phrase,
    infer_requesting_authority_gender,
    requisition_authority_clause,
)
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP


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
