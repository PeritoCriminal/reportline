"""
Extração de metadados de caso a partir de documentos e prompt.

Interface preparada para integração com IA; a implementação atual
retorna metadados vazios na inferência, preservando merge com o formulário.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.metadata_merge import merge_case_metadata


def infer_case_metadata_from_documents(
    *,
    uploaded_files: list | None = None,
    supplementary_prompt: str = "",
) -> CaseMetadata:
    """
    Infere metadados a partir de documentos em memória e prompt complementar.

    Stub até integração com serviço de IA; não persiste arquivos recebidos.
    """
    _ = uploaded_files
    _ = supplementary_prompt
    return CaseMetadata()


def extract_case_metadata(
    *,
    form_data: CaseMetadata,
    uploaded_files: list | None = None,
) -> CaseMetadata:
    """
    Enriquece metadados do caso com base em documentos e prompt.

    Valores informados manualmente pelo perito prevalecem sobre a inferência.
    """
    inferred = infer_case_metadata_from_documents(
        uploaded_files=uploaded_files,
        supplementary_prompt=form_data.supplementary_prompt,
    )
    return merge_case_metadata(form_data, inferred)
