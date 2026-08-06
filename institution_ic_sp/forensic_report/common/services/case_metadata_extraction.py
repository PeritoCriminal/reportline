"""
Extração de metadados de caso a partir de documentos e prompt.

A inferência é acionada pela análise prévia de documentos no intake comum;
o submit final usa apenas os dados revisados pelo perito.
"""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.metadata_merge import merge_case_metadata
from institution_ic_sp.forensic_report.registry import (
    GENERIC_WORKFLOW,
    get_metadata_inference_callable,
    get_workflow,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    build_field_coverage_from_ai_payload,
    merge_field_coverage_with_metadata,
)
from institution_ic_sp.forensic_report.workflows.initial_data.ai.services.metadata_inference import (
    infer_case_metadata_ai_payload,
)
from institution_ic_sp.forensic_report.common.ai.structured_output import case_metadata_from_ai_payload


def infer_case_metadata_from_documents(
    *,
    uploaded_files: list[UploadedFile] | None = None,
    supplementary_prompt: str = "",
    workflow_slug: str = GENERIC_WORKFLOW.slug,
) -> CaseMetadata:
    """
    Infere metadados a partir de documentos em memória e prompt complementar.

    Delega ao handler registrado para o workflow informado.
    """
    workflow = get_workflow(workflow_slug)
    inference = get_metadata_inference_callable(workflow)
    return inference(
        uploaded_files=uploaded_files,
        supplementary_prompt=supplementary_prompt,
    )


def analyze_case_metadata_from_documents(
    *,
    manual: CaseMetadata,
    uploaded_files: list[UploadedFile] | None = None,
    workflow_slug: str = GENERIC_WORKFLOW.slug,
) -> CaseMetadata:
    """
    Combina formulário parcial com inferência documental para pré-preenchimento.

    Valores já informados manualmente pelo perito prevalecem sobre a IA.
    """
    inferred = infer_case_metadata_from_documents(
        uploaded_files=uploaded_files,
        supplementary_prompt=manual.supplementary_prompt,
        workflow_slug=workflow_slug,
    )
    return merge_case_metadata(manual, inferred)


def analyze_case_metadata_with_coverage(
    *,
    manual: CaseMetadata,
    uploaded_files: list[UploadedFile] | None = None,
    workflow_slug: str = GENERIC_WORKFLOW.slug,
) -> tuple[CaseMetadata, dict[str, str]]:
    """
    Combina intake parcial com inferência documental e mapa de cobertura da IA.

    A cobertura orienta prompts inline (datas vazias, data sem hora, etc.).
    """
    payload = infer_case_metadata_ai_payload(
        uploaded_files=uploaded_files,
        supplementary_prompt=manual.supplementary_prompt,
    )
    inferred = case_metadata_from_ai_payload(payload) if payload else CaseMetadata()
    merged = merge_case_metadata(manual, inferred)
    coverage = build_field_coverage_from_ai_payload(payload)
    return merged, merge_field_coverage_with_metadata(merged, coverage)
