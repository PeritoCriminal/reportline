"""
Extração de metadados de caso a partir de documentos e prompt.

Interface preparada para integração com IA; a implementação atual
reutiliza apenas os valores já informados pelo perito no formulário.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata


def extract_case_metadata(
    *,
    form_data: CaseMetadata,
    uploaded_files: list | None = None,
) -> CaseMetadata:
    """
    Enriquece metadados do caso com base em documentos e prompt.

    Enquanto a integração de IA não estiver disponível, retorna cópia
    dos dados informados manualmente pelo perito.
    """
    _ = uploaded_files
    return CaseMetadata(
        report_number=form_data.report_number,
        report_year=form_data.report_year,
        service_protocol=form_data.service_protocol,
        requester=form_data.requester,
        case_type=form_data.case_type,
        bulletin_number=form_data.bulletin_number,
        exam_objective=form_data.exam_objective,
        supplementary_prompt=form_data.supplementary_prompt,
        uploaded_file_names=list(form_data.uploaded_file_names),
    )
