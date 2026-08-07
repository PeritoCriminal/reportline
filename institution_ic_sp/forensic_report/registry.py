# reportline/institution_ic_sp/forensic_report/registry.py
"""
Registro de workflows de laudo pericial disponíveis no IC-SP.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile

    from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata


MetadataInferenceCallable = Callable[
    ["list[UploadedFile] | None", str],
    "CaseMetadata",
]

_LEGACY_WORKFLOW_ALIASES: dict[str, str] = {
    "generic": "initial_data",
}


@dataclass(frozen=True)
class ForensicReportWorkflow:
    """Metadados de um tipo de laudo pericial suportado."""

    slug: str
    label: str
    description: str
    metadata_inference_path: str = ""


INITIAL_DATA_WORKFLOW = ForensicReportWorkflow(
    slug="initial_data",
    label="Dados iniciais do laudo",
    description=(
        "Estrutura padrão com preâmbulo, objetivo, dados da requisição "
        "e do atendimento, pronta para edição no editor."
    ),
    metadata_inference_path=(
        "institution_ic_sp.forensic_report.workflows.initial_data.ai.services."
        "metadata_inference.infer_case_metadata"
    ),
)

PROPERTY_CRIME_WORKFLOW = ForensicReportWorkflow(
    slug="property_crime",
    label="Crime patrimonial",
    description=(
        "Exame de local e características do imóvel em ocorrências "
        "de furto, roubo ou dano patrimonial."
    ),
)

# Alias legado — preferir INITIAL_DATA_WORKFLOW em código novo.
GENERIC_WORKFLOW = INITIAL_DATA_WORKFLOW

WORKFLOW_REGISTRY: dict[str, ForensicReportWorkflow] = {
    INITIAL_DATA_WORKFLOW.slug: INITIAL_DATA_WORKFLOW,
    PROPERTY_CRIME_WORKFLOW.slug: PROPERTY_CRIME_WORKFLOW,
}


def get_workflow(slug: str) -> ForensicReportWorkflow:
    """Retorna workflow registrado ou levanta ``KeyError``."""
    resolved_slug = _LEGACY_WORKFLOW_ALIASES.get(slug, slug)
    return WORKFLOW_REGISTRY[resolved_slug]


def get_metadata_inference_callable(workflow: ForensicReportWorkflow) -> MetadataInferenceCallable:
    """Resolve função de inferência de metadados registrada no workflow."""
    if not workflow.metadata_inference_path:
        raise ValueError(f"Workflow {workflow.slug} não possui inferência de metadados.")

    module_path, function_name = workflow.metadata_inference_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    callback = getattr(module, function_name)
    if not callable(callback):
        raise TypeError(f"{workflow.metadata_inference_path} não é chamável.")
    return callback
