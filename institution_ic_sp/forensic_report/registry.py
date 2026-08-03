"""
Registro de workflows de laudo pericial disponíveis no IC-SP.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ForensicReportWorkflow:
    """Metadados de um tipo de laudo pericial suportado."""

    slug: str
    label: str
    description: str


GENERIC_WORKFLOW = ForensicReportWorkflow(
    slug="generic",
    label="Laudo pericial genérico",
    description=(
        "Estrutura padrão com preâmbulo, objetivo, dados da requisição "
        "e do atendimento, pronta para edição no editor."
    ),
)

WORKFLOW_REGISTRY: dict[str, ForensicReportWorkflow] = {
    GENERIC_WORKFLOW.slug: GENERIC_WORKFLOW,
}


def get_workflow(slug: str) -> ForensicReportWorkflow:
    """Retorna workflow registrado ou levanta ``KeyError``."""
    return WORKFLOW_REGISTRY[slug]
