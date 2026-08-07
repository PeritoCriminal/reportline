# reportline/institution_ic_sp/forensic_report/services/trace_observation_continuation.py
"""
Coleta e persistência de vestígios (Elementos Observados) após a seção de local.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.exam_category import (
    is_property_scene_category,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    STATE_COLLECTING_COLLECTED_ITEMS,
    STATE_COLLECTING_TRACES,
    attach_bootstrap_meta,
    get_bootstrap_meta,
    metadata_from_bootstrap,
)
from institution_ic_sp.forensic_report.workflows.property_crime.ai.services.trace_observation_inference import (
    infer_trace_observation_content,
)
from reports.models import Report
from reports.services.report_image_attachments import (
    ReportImageAttachment,
    report_image_attachments_to_payload,
)

COLLECTED_ITEMS_TODO_MESSAGE = (
    "A coleta de objetos e peças será implementada em breve. "
    "Continue editando o laudo normalmente."
)

TRACES_SECTION_HEADING = "Elementos Observados"


def traces_from_bootstrap(page_layout: dict | None) -> list[dict[str, object]]:
    """Retorna vestígios coletados no bootstrap."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("traces", [])
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        inferred = item.get("inferred", {})
        if not isinstance(inferred, dict):
            inferred = {}
        images = item.get("images", [])
        if not isinstance(images, list):
            images = []
        normalized.append(
            {
                "prompt": str(item.get("prompt", "")).strip(),
                "images": images,
                "inferred": {
                    "trace_paragraph": str(inferred.get("trace_paragraph", "")).strip(),
                    "report_images": inferred.get("report_images", [])
                    if isinstance(inferred.get("report_images"), list)
                    else [],
                },
            }
        )
    return normalized


def trace_at_index(page_layout: dict | None, index: int) -> dict[str, object] | None:
    """Retorna vestígio na posição informada ou ``None``."""
    traces = traces_from_bootstrap(page_layout)
    if index < 0 or index >= len(traces):
        return None
    return traces[index]


def is_traces_collection_active(page_layout: dict | None) -> bool:
    """Indica se o laudo está na fase interativa de coleta de vestígios."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    return bool(bootstrap.get("traces_collection_active")) and not bootstrap.get(
        "traces_completed"
    )


def complete_traces_collection(
    report: Report,
    *,
    skipped: bool = False,
) -> Report:
    """
    Encerra loop de vestígios e abre stub de objetos/peças coletadas.

    ``skipped=True`` quando o perito recusa incluir vestígios na primeira pergunta.
    """
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    bootstrap["traces_completed"] = True
    bootstrap["traces_collection_active"] = False
    if skipped:
        bootstrap["traces_skipped"] = True
    bootstrap["state"] = STATE_COLLECTING_COLLECTED_ITEMS
    bootstrap.pop("build_progress", None)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])

    from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
        persist_property_crime_phase,
    )

    metadata = metadata_from_bootstrap(report.page_layout)
    persist_property_crime_phase(report, metadata)
    return report


def save_trace_observation(
    report: Report,
    *,
    prompt: str = "",
    images: list[ReportImageAttachment] | None = None,
    allow_external_images: bool = False,
    audit_context: dict | None = None,
) -> Report:
    """
    Infere conteúdo de um vestígio, persiste no bootstrap e inicia montagem incremental.
    """
    metadata = metadata_from_bootstrap(report.page_layout)
    if not is_property_scene_category(metadata.exam_category):
        raise ValueError("Vestígios só estão disponíveis para exame de local patrimonial.")

    attachments = list(images or [])
    if not prompt.strip() and not attachments:
        raise ValueError("Informe imagens ou orientações sobre o vestígio.")

    content = infer_trace_observation_content(
        report=report,
        metadata=metadata,
        trace_prompt=prompt,
        trace_image_attachments=attachments,
        allow_external_images=allow_external_images,
        audit_context=audit_context,
    )

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    traces = traces_from_bootstrap(report.page_layout)
    trace_index = len(traces)
    traces.append(
        {
            "prompt": prompt.strip(),
            "images": report_image_attachments_to_payload(attachments),
            "inferred": content,
        }
    )
    bootstrap["traces"] = traces
    bootstrap["traces_collection_active"] = True
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)

    from institution_ic_sp.forensic_report.services.forensic_report_body_incremental import (
        start_traces_build_phase,
    )

    start_traces_build_phase(report, trace_index=trace_index)
    return report


def start_traces_collection_after_scene(report: Report) -> Report:
    """Abre coleta de vestígios após montagem da seção de local."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    bootstrap["traces_collection_active"] = True
    bootstrap["traces"] = list(bootstrap.get("traces") or [])
    bootstrap["traces_heading_inserted"] = bool(bootstrap.get("traces_heading_inserted"))
    bootstrap["state"] = STATE_COLLECTING_TRACES
    bootstrap.pop("build_progress", None)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
