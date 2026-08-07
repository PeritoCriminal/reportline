# reportline/institution_ic_sp/forensic_report/common/services/case_metadata_extraction.py
"""
Extração de metadados de caso a partir de documentos e prompt.

A inferência é acionada pela análise prévia de documentos no intake comum;
o submit final usa apenas os dados revisados pelo perito.
"""

from __future__ import annotations

from dataclasses import replace

from django.core.files.uploadedfile import UploadedFile

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_UNKNOWN,
    infer_exam_category_from_text,
    normalize_exam_category,
)
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
from institution_ic_sp.forensic_report.common.ai.structured_output import (
    case_metadata_from_ai_payload,
    extensions_from_ai_payload,
)


def resolve_exam_category(metadata: CaseMetadata) -> CaseMetadata:
    """
    Completa ``exam_category`` quando a IA deixou ``unknown`` mas o texto é explícito.

    Usa objetivo do exame e orientações complementares do perito como fonte.
    """
    if normalize_exam_category(metadata.exam_category) != EXAM_CATEGORY_UNKNOWN:
        return metadata

    inferred = infer_exam_category_from_text(
        metadata.exam_objective,
        metadata.supplementary_prompt,
    )
    if inferred == EXAM_CATEGORY_UNKNOWN:
        return metadata
    return replace(metadata, exam_category=inferred)


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
    audit_context: dict | None = None,
) -> tuple[CaseMetadata, dict[str, object]]:
    """
    Combina formulário parcial com inferência documental para pré-preenchimento.

    Valores já informados manualmente pelo perito prevalecem sobre a IA.
    Retorna metadados mesclados e objeto ``extensions`` inferido.
    """
    payload = infer_case_metadata_ai_payload(
        uploaded_files=uploaded_files,
        supplementary_prompt=manual.supplementary_prompt,
        audit_context=audit_context,
    )
    inferred = case_metadata_from_ai_payload(payload) if payload else CaseMetadata()
    merged = merge_case_metadata(manual, inferred)
    merged = resolve_exam_category(merged)
    return merged, extensions_from_ai_payload(payload)


def analyze_case_metadata_with_coverage(
    *,
    manual: CaseMetadata,
    uploaded_files: list[UploadedFile] | None = None,
    workflow_slug: str = GENERIC_WORKFLOW.slug,
    audit_context: dict | None = None,
) -> tuple[CaseMetadata, dict[str, str], dict[str, object]]:
    """
    Combina intake parcial com inferência documental e mapa de cobertura da IA.

    A cobertura orienta prompts inline (datas vazias, data sem hora, etc.).
    """
    payload = infer_case_metadata_ai_payload(
        uploaded_files=uploaded_files,
        supplementary_prompt=manual.supplementary_prompt,
        audit_context=audit_context,
    )
    inferred = case_metadata_from_ai_payload(payload) if payload else CaseMetadata()
    merged = merge_case_metadata(manual, inferred)
    merged = resolve_exam_category(merged)
    coverage = build_field_coverage_from_ai_payload(payload)
    return (
        merged,
        merge_field_coverage_with_metadata(merged, coverage),
        extensions_from_ai_payload(payload),
    )
