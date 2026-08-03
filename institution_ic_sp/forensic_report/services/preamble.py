"""
Texto de preâmbulo do laudo pericial genérico.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata


def build_preamble_paragraph(metadata: CaseMetadata) -> str:
    """
    Monta parágrafo introdutório com base nos metadados disponíveis.

    Omite trechos cujos campos estejam vazios, evitando frases incompletas.
    """
    clauses: list[str] = []

    if metadata.requester.strip():
        clauses.append(f"em atendimento à requisição de {metadata.requester.strip()}")

    if metadata.service_protocol.strip():
        clauses.append(
            f"referente ao protocolo de atendimento nº {metadata.service_protocol.strip()}"
        )

    if metadata.bulletin_number.strip():
        clauses.append(
            f"relacionado ao boletim de ocorrência nº {metadata.bulletin_number.strip()}"
        )

    if metadata.case_type.strip():
        clauses.append(f"classificado como {metadata.case_type.strip()}")

    if not clauses:
        return (
            "Trata-se de laudo pericial elaborado nos termos da legislação "
            "e normas técnicas aplicáveis à perícia criminalística."
        )

    joined = ", ".join(clauses)
    return f"Trata-se de laudo pericial elaborado {joined}."
