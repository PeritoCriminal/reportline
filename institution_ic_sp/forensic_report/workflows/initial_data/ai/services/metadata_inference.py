# reportline/institution_ic_sp/forensic_report/workflows/initial_data/ai/services/metadata_inference.py
"""
Inferência de metadados do intake inicial a partir de documentos.
"""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile

from institution_ic_sp.forensic_report.common.ai.gateway import (
    complete_json_chat_safe,
    sanitize_uploaded_document_text,
)
from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads
from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_case_metadata_schema_summary,
    load_prompt_markdown,
    render_prompt_template,
)
from institution_ic_sp.forensic_report.common.ai.structured_output import case_metadata_from_ai_payload
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.registry import INITIAL_DATA_WORKFLOW


def infer_case_metadata(
    *,
    uploaded_files: list[UploadedFile] | None = None,
    supplementary_prompt: str = "",
    audit_context: dict | None = None,
) -> CaseMetadata:
    """
    Infere metadados administrativos a partir de uploads em memória.

    Retorna metadados vazios quando não houver texto extraído ou a IA falhar.
    """
    document_excerpts = extract_text_from_uploads(uploaded_files)
    if not document_excerpts:
        return CaseMetadata()

    document_excerpts = sanitize_uploaded_document_text(
        document_excerpts,
        audit_context=audit_context,
    )

    system_prompt = load_prompt_markdown(
        workflow_slug=INITIAL_DATA_WORKFLOW.slug,
        task="metadata_extraction",
        name="system",
    )
    user_template = load_prompt_markdown(
        workflow_slug=INITIAL_DATA_WORKFLOW.slug,
        task="metadata_extraction",
        name="user",
    )
    user_prompt = render_prompt_template(
        user_template,
        document_excerpts=document_excerpts,
        supplementary_prompt=supplementary_prompt.strip() or "(nenhuma)",
        output_schema_summary=load_case_metadata_schema_summary(),
    )

    payload = complete_json_chat_safe(
        system=system_prompt,
        user=user_prompt,
        audit_context=audit_context,
    )
    if payload is None:
        return CaseMetadata()

    return case_metadata_from_ai_payload(payload)


def infer_case_metadata_ai_payload(
    *,
    uploaded_files: list[UploadedFile] | None = None,
    supplementary_prompt: str = "",
    audit_context: dict | None = None,
) -> dict | None:
    """
    Retorna JSON bruto inferido pela IA ou ``None`` quando indisponível.

    Usado para classificar cobertura parcial de datas e horas no bootstrap.
    """
    document_excerpts = extract_text_from_uploads(uploaded_files)
    if not document_excerpts:
        return None

    document_excerpts = sanitize_uploaded_document_text(
        document_excerpts,
        audit_context=audit_context,
    )

    system_prompt = load_prompt_markdown(
        workflow_slug=INITIAL_DATA_WORKFLOW.slug,
        task="metadata_extraction",
        name="system",
    )
    user_template = load_prompt_markdown(
        workflow_slug=INITIAL_DATA_WORKFLOW.slug,
        task="metadata_extraction",
        name="user",
    )
    user_prompt = render_prompt_template(
        user_template,
        document_excerpts=document_excerpts,
        supplementary_prompt=supplementary_prompt.strip() or "(nenhuma)",
        output_schema_summary=load_case_metadata_schema_summary(),
    )

    return complete_json_chat_safe(
        system=system_prompt,
        user=user_prompt,
        audit_context=audit_context,
    )
