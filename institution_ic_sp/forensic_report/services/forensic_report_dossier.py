# reportline/institution_ic_sp/forensic_report/services/forensic_report_dossier.py
"""
Persistência do dossiê pericial confirmado por fase de workflow.

Centraliza gravação dos dados validados pelo perito após cada etapa,
separando memória de caso do estado transitório de bootstrap.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.exam_category import (
    is_property_scene_category,
    normalize_exam_category,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    _supplementary_prompt_from_bootstrap_payload,
    extensions_from_bootstrap,
    field_coverage_from_bootstrap,
    get_bootstrap_meta,
    skipped_prompts_from_bootstrap,
)
from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
    scene_attendance_context_from_bootstrap,
    scene_attendance_context_to_payload,
)
from institution_ic_sp.forensic_report.services.scene_examination_continuation import (
    scene_characteristics_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.scene_examination_content import (
    scene_examination_content_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.trace_observation_continuation import (
    traces_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    ALL_PROMPT_FIELD_NAMES,
)
from institution_ic_sp.models import ForensicReportMetadata
from reports.models import Report

INITIAL_DATA_PHASE = "initial_data"
PROPERTY_CRIME_PHASE = "property_crime"

DOSSIER_DATA_FIELD_NAMES: frozenset[str] = frozenset(
    field.name for field in fields(CaseMetadata) if field.name != "supplementary_prompt"
)


def get_forensic_report_metadata(report: Report) -> ForensicReportMetadata | None:
    """Retorna dossiê persistido do laudo ou ``None`` quando ausente."""
    return ForensicReportMetadata.objects.filter(report=report).first()


def get_or_create_forensic_report_metadata(report: Report) -> ForensicReportMetadata:
    """Obtém ou cria registro de dossiê vinculado ao laudo."""
    metadata, _created = ForensicReportMetadata.objects.get_or_create(
        report=report,
        defaults={"data": {}},
    )
    return metadata


def initial_data_phase_from_dossier(report: Report) -> dict[str, Any] | None:
    """Retorna fase ``initial_data`` confirmada ou ``None``."""
    return _phase_from_dossier(report, INITIAL_DATA_PHASE)


def property_crime_phase_from_dossier(report: Report) -> dict[str, Any] | None:
    """Retorna fase ``property_crime`` confirmada ou ``None``."""
    return _phase_from_dossier(report, PROPERTY_CRIME_PHASE)


def _phase_from_dossier(report: Report, phase_key: str) -> dict[str, Any] | None:
    """Retorna cópia de uma fase confirmada do dossiê ou ``None``."""
    dossier = get_forensic_report_metadata(report)
    if dossier is None:
        return None
    phases = dossier.data.get("phases", {})
    if not isinstance(phases, dict):
        return None
    phase = phases.get(phase_key)
    return deepcopy(phase) if isinstance(phase, dict) else None


def initial_data_extensions_for_report(report: Report) -> dict[str, Any]:
    """
    Retorna extensions confirmadas da fase ``initial_data`` ou do bootstrap.

    Prioriza o dossiê persistido; usa bootstrap quando a fase ainda não foi gravada.
    """
    phase = initial_data_phase_from_dossier(report)
    if isinstance(phase, dict):
        data = phase.get("data", {})
        if isinstance(data, dict):
            extensions = data.get("extensions", {})
            if isinstance(extensions, dict) and extensions:
                return deepcopy(extensions)
    return extensions_from_bootstrap(report.page_layout)


def _manual_prompt_fields_from_bootstrap(page_layout: dict[str, Any] | None) -> set[str]:
    """Lista campos preenchidos manualmente via prompts inline."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("manual_prompt_fields", [])
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item) in ALL_PROMPT_FIELD_NAMES}


def _document_count_from_bootstrap(page_layout: dict[str, Any] | None) -> int:
    """Retorna quantidade de documentos analisados na última extração."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("document_count")
    if isinstance(raw, int) and raw >= 0:
        return raw
    return 0


def _serialize_dossier_value(value: object) -> object:
    """Converte valores de ``CaseMetadata`` para JSON persistível."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        localized = timezone.localtime(value) if timezone.is_aware(value) else value
        return localized.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, int):
        return value
    return str(value)


def case_metadata_to_dossier_data(
    metadata: CaseMetadata,
    page_layout: dict[str, Any] | None,
) -> dict[str, object]:
    """Serializa campos administrativos confirmados para o dossiê."""
    payload: dict[str, object] = {}
    for field_name in DOSSIER_DATA_FIELD_NAMES:
        payload[field_name] = _serialize_dossier_value(getattr(metadata, field_name))
    payload["extensions"] = extensions_from_bootstrap(page_layout)
    return payload


def _field_has_confirmed_value(metadata: CaseMetadata, field_name: str) -> bool:
    """Indica se campo administrativo possui valor confirmado."""
    value = getattr(metadata, field_name)
    if field_name == "report_year":
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def build_field_provenance(
    metadata: CaseMetadata,
    *,
    skipped_fields: set[str],
    manual_fields: set[str],
) -> dict[str, str]:
    """Monta origem de cada campo confirmado na fase inicial."""
    provenance: dict[str, str] = {}
    for field_name in DOSSIER_DATA_FIELD_NAMES:
        if field_name in skipped_fields:
            provenance[field_name] = "skipped"
        elif field_name in manual_fields:
            provenance[field_name] = "manual"
        elif _field_has_confirmed_value(metadata, field_name):
            provenance[field_name] = "ai"
    return provenance


def _supplementary_prompt_for_phase(page_layout: dict[str, Any] | None, metadata: CaseMetadata) -> str:
    """Recupera orientações complementares do perito para o dossiê."""
    cleaned = metadata.supplementary_prompt.strip()
    if cleaned:
        return cleaned
    bootstrap = get_bootstrap_meta(page_layout) or {}
    return _supplementary_prompt_from_bootstrap_payload(bootstrap)


def build_initial_data_phase_payload(
    report: Report,
    metadata: CaseMetadata,
) -> dict[str, Any]:
    """Monta estrutura da fase ``initial_data`` a partir do bootstrap confirmado."""
    page_layout = report.page_layout
    skipped_fields = skipped_prompts_from_bootstrap(page_layout)
    manual_fields = _manual_prompt_fields_from_bootstrap(page_layout)
    coverage = field_coverage_from_bootstrap(page_layout)

    return {
        "inputs": {
            "supplementary_prompt": _supplementary_prompt_for_phase(page_layout, metadata),
            "document_count": _document_count_from_bootstrap(page_layout),
        },
        "data": case_metadata_to_dossier_data(metadata, page_layout),
        "meta": {
            "confirmed_at": timezone.now().isoformat(),
            "skipped_fields": sorted(skipped_fields),
            "field_coverage": dict(coverage),
            "field_provenance": build_field_provenance(
                metadata,
                skipped_fields=skipped_fields,
                manual_fields=manual_fields,
            ),
        },
    }


@transaction.atomic
def persist_initial_data_phase(report: Report, metadata: CaseMetadata) -> ForensicReportMetadata:
    """
    Grava fase ``initial_data`` no dossiê após confirmação e montagem administrativa.

    Substitui conteúdo anterior da mesma fase quando o laudo for reprocessado.
    """
    dossier = get_or_create_forensic_report_metadata(report)
    payload = deepcopy(dossier.data) if isinstance(dossier.data, dict) else {}
    phases = dict(payload.get("phases", {})) if isinstance(payload.get("phases"), dict) else {}
    phases[INITIAL_DATA_PHASE] = build_initial_data_phase_payload(report, metadata)
    payload["phases"] = phases
    payload["exam_category"] = normalize_exam_category(metadata.exam_category)
    dossier.data = payload
    dossier.save(update_fields=["data", "updated_at"])
    return dossier


def _location_inputs_payload(location: dict[str, object]) -> dict[str, str]:
    """Normaliza local informado para gravação no dossiê."""
    if not location:
        return {
            "kind": "",
            "address": "",
            "latitude": "",
            "longitude": "",
        }
    return {
        "kind": str(location.get("kind", "")).strip(),
        "address": str(location.get("address", "")).strip(),
        "latitude": str(location.get("latitude", "")).strip(),
        "longitude": str(location.get("longitude", "")).strip(),
    }


def _build_sources_used(
    report: Report,
    *,
    scene_prompt: str,
    image_ids: list[str],
    location: dict[str, object],
    attendance_context: dict[str, str] | None = None,
) -> list[str]:
    """Lista fontes consideradas na inferência de exame de local."""
    sources: list[str] = []
    if initial_data_phase_from_dossier(report):
        sources.append("initial_data")
    if scene_prompt.strip():
        sources.append("scene_prompt")
    if image_ids:
        sources.append("images")
    if any(_location_inputs_payload(location).values()):
        sources.append("location")
    context_values = attendance_context or {}
    if any(str(value).strip() for value in context_values.values()):
        sources.append("attendance_context")
    return sources


def build_property_crime_phase_payload(
    report: Report,
    metadata: CaseMetadata,
) -> dict[str, Any]:
    """Monta estrutura da fase ``property_crime`` a partir do bootstrap confirmado."""
    page_layout = report.page_layout
    characteristics = scene_characteristics_from_bootstrap(page_layout)
    content = scene_examination_content_from_bootstrap(page_layout)
    location = characteristics.get("location", {})
    if not isinstance(location, dict):
        location = {}
    scene_prompt = str(characteristics.get("prompt", "")).strip()
    image_ids = [
        str(item) for item in characteristics.get("image_ids", []) if str(item).strip()
    ]
    scene_images = characteristics.get("images", [])
    if not isinstance(scene_images, list):
        scene_images = []
    attendance_context = scene_attendance_context_to_payload(
        scene_attendance_context_from_bootstrap(page_layout)
    )
    report_images = content.get("report_images", [])
    if not isinstance(report_images, list):
        report_images = []
    traces = traces_from_bootstrap(page_layout)

    return {
        "inputs": {
            "scene_prompt": scene_prompt,
            "image_ids": image_ids,
            "images": scene_images,
            "location": _location_inputs_payload(location),
            "attendance_context": attendance_context,
            "traces": [
                {
                    "prompt": str(item.get("prompt", "")).strip(),
                    "images": item.get("images", []) if isinstance(item.get("images"), list) else [],
                }
                for item in traces
            ],
        },
        "data": {
            "exam_category": normalize_exam_category(metadata.exam_category),
            "characteristics_heading": content.get("characteristics_heading", ""),
            "attendance_context_paragraph": content.get("attendance_context_paragraph", ""),
            "characteristics_paragraph": content.get("characteristics_paragraph", ""),
            "report_images": report_images,
            "traces": [
                {
                    "trace_paragraph": str(
                        (item.get("inferred") or {}).get("trace_paragraph", "")
                    ).strip(),
                    "report_images": (item.get("inferred") or {}).get("report_images", [])
                    if isinstance((item.get("inferred") or {}).get("report_images"), list)
                    else [],
                }
                for item in traces
                if isinstance(item, dict)
            ],
        },
        "meta": {
            "confirmed_at": timezone.now().isoformat(),
            "sources_used": _build_sources_used(
                report,
                scene_prompt=scene_prompt,
                image_ids=image_ids,
                location=location,
                attendance_context=attendance_context,
            ),
        },
    }


@transaction.atomic
def persist_property_crime_phase(report: Report, metadata: CaseMetadata) -> ForensicReportMetadata:
    """
    Grava fase ``property_crime`` após montagem da seção de exame de local.

    Ignora laudos cuja categoria não corresponda a exame de local patrimonial.
    """
    if not is_property_scene_category(metadata.exam_category):
        dossier = get_forensic_report_metadata(report)
        if dossier is None:
            dossier = get_or_create_forensic_report_metadata(report)
        payload = deepcopy(dossier.data) if isinstance(dossier.data, dict) else {}
        payload["exam_category"] = normalize_exam_category(metadata.exam_category)
        dossier.data = payload
        dossier.save(update_fields=["data", "updated_at"])
        return dossier

    dossier = get_or_create_forensic_report_metadata(report)
    payload = deepcopy(dossier.data) if isinstance(dossier.data, dict) else {}
    phases = dict(payload.get("phases", {})) if isinstance(payload.get("phases"), dict) else {}
    phases[PROPERTY_CRIME_PHASE] = build_property_crime_phase_payload(report, metadata)
    payload["phases"] = phases
    payload["exam_category"] = normalize_exam_category(metadata.exam_category)
    dossier.data = payload
    dossier.save(update_fields=["data", "updated_at"])
    return dossier
