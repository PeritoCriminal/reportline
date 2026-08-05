"""
Inferência de metadados do intake genérico a partir de documentos.
"""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile

from institution_ic_sp.forensic_report.common.ai.client import complete_json_chat
from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads
from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_case_metadata_schema_summary,
    load_prompt_markdown,
    render_prompt_template,
)
from institution_ic_sp.forensic_report.common.ai.structured_output import case_metadata_from_ai_payload
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW


def infer_case_metadata(
    *,
    uploaded_files: list[UploadedFile] | None = None,
    supplementary_prompt: str = "",
) -> CaseMetadata:
    """
    Infere metadados administrativos a partir de uploads em memória.

    Retorna metadados vazios quando não houver texto extraído ou a IA falhar.
    """
    document_excerpts = extract_text_from_uploads(uploaded_files)
    if not document_excerpts:
        return CaseMetadata()

    system_prompt = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="metadata_extraction",
        name="system",
    )
    user_template = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="metadata_extraction",
        name="user",
    )
    user_prompt = render_prompt_template(
        user_template,
        document_excerpts=document_excerpts,
        supplementary_prompt=supplementary_prompt.strip() or "(nenhuma)",
        output_schema_summary=load_case_metadata_schema_summary(),
    )

    payload = complete_json_chat(system=system_prompt, user=user_prompt)
    if payload is None:
        return CaseMetadata()

    return case_metadata_from_ai_payload(payload)


def infer_case_metadata_ai_payload(
    *,
    uploaded_files: list[UploadedFile] | None = None,
    supplementary_prompt: str = "",
) -> dict | None:
    """
    Retorna JSON bruto inferido pela IA ou ``None`` quando indisponível.

    Usado para classificar cobertura parcial de datas e horas no bootstrap.
    """
    document_excerpts = extract_text_from_uploads(uploaded_files)
    if not document_excerpts:
        return None

    system_prompt = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="metadata_extraction",
        name="system",
    )
    user_template = load_prompt_markdown(
        workflow_slug=GENERIC_WORKFLOW.slug,
        task="metadata_extraction",
        name="user",
    )
    user_prompt = render_prompt_template(
        user_template,
        document_excerpts=document_excerpts,
        supplementary_prompt=supplementary_prompt.strip() or "(nenhuma)",
        output_schema_summary=load_case_metadata_schema_summary(),
    )

    return complete_json_chat(system=system_prompt, user=user_prompt)
