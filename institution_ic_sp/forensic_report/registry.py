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


@dataclass(frozen=True)
class ForensicReportWorkflow:
    """Metadados de um tipo de laudo pericial suportado."""

    slug: str
    label: str
    description: str
    metadata_inference_path: str = ""


GENERIC_WORKFLOW = ForensicReportWorkflow(
    slug="generic",
    label="Laudo pericial genérico",
    description=(
        "Estrutura padrão com preâmbulo, objetivo, dados da requisição "
        "e do atendimento, pronta para edição no editor."
    ),
    metadata_inference_path=(
        "institution_ic_sp.forensic_report.workflows.generic.ai.services."
        "metadata_inference.infer_case_metadata"
    ),
)

WORKFLOW_REGISTRY: dict[str, ForensicReportWorkflow] = {
    GENERIC_WORKFLOW.slug: GENERIC_WORKFLOW,
}


def get_workflow(slug: str) -> ForensicReportWorkflow:
    """Retorna workflow registrado ou levanta ``KeyError``."""
    return WORKFLOW_REGISTRY[slug]


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
