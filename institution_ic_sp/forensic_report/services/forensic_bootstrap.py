"""
Estado de bootstrap interativo de laudos periciais.

Persiste progresso e metadados em ``page_layout.reportline_meta.bootstrap``
sem migration dedicada no model ``Report``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from django.http import QueryDict

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_from_post,
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    ALL_PROMPT_FIELD_NAMES,
    DATETIME_PROMPT_FIELD_NAMES,
    default_prompt_value,
    is_prompt_field_value_empty,
    merge_field_coverage_with_metadata,
)
from reports.models import Report
from reports.services.report_kind import REPORTLINE_META_KEY, is_forensic_report

BOOTSTRAP_META_KEY = "bootstrap"

STATE_SHELL_CREATED = "shell_created"
STATE_COLLECTING_SCENE_CONTINUATION = "collecting_scene_continuation"
STATE_ANALYZED = "analyzed"
STATE_COLLECTING_PROMPTS = "collecting_prompts"
STATE_BUILDING = "building"
STATE_PROMPTING = "prompting"
STATE_READY = "ready"

CRITICAL_PROMPT_FIELDS: tuple[tuple[str, str], ...] = (
    ("report_number", "Número do laudo"),
    ("exam_objective", "Objetivo do exame"),
    ("requesting_authority", "Autoridade requisitante"),
    ("police_district", "Distrito policial / Delegacia"),
    ("occurrence_report", "Boletim de ocorrência"),
    ("police_inquiry", "Inquérito policial"),
    ("designation_date", "Data da designação"),
    ("occurrence_at", "Data e hora da ocorrência"),
    ("requisition_at", "Data e hora da requisição"),
    ("attendance_protocol", "Número do protocolo"),
    ("examination_at", "Data e hora do exame"),
    ("photography", "Fotógrafo"),
    ("scanning_3d", "Escaneamento 3D"),
    ("sketch", "Croqui"),
)

PROMPT_FIELD_CONFIG: dict[str, dict[str, str]] = {
    "report_number": {
        "label": "Número do laudo",
        "input_type": "text",
        "help_text": "Informe a numeração sequencial do laudo, sem o ano. Se pular, o título permanecerá genérico.",
        "placeholder": "Ex.: 42",
    },
    "exam_objective": {
        "label": "Objetivo do exame",
        "input_type": "text",
        "help_text": "Descreva o objetivo pericial identificado nos documentos.",
        "placeholder": "",
    },
    "requesting_authority": {
        "label": "Autoridade requisitante",
        "input_type": "text",
        "help_text": "Delegado ou autoridade que requisitou o exame.",
        "placeholder": "",
    },
    "police_district": {
        "label": "Distrito policial / Delegacia",
        "input_type": "text",
        "help_text": "Unidade policial requisitante identificada nos documentos.",
        "placeholder": "",
    },
    "occurrence_report": {
        "label": "Boletim de ocorrência",
        "input_type": "text",
        "help_text": "Número ou referência do BO, se constar nos documentos.",
        "placeholder": "Ex.: BO-12345/2026",
    },
    "police_inquiry": {
        "label": "Inquérito policial",
        "input_type": "text",
        "help_text": "Número ou referência do IP, se constar nos documentos.",
        "placeholder": "Ex.: IP-12345/2026",
    },
    "designation_date": {
        "label": "Data da designação",
        "input_type": "date",
        "help_text": "Data em que o perito foi designado para o exame.",
        "placeholder": "",
    },
    "occurrence_at": {
        "label": "Data e hora da ocorrência",
        "input_type": "datetime-local",
        "help_text": "Momento da ocorrência, quando informado na requisição.",
        "placeholder": "",
    },
    "requisition_at": {
        "label": "Data e hora da requisição",
        "input_type": "datetime-local",
        "help_text": "Momento da requisição pericial nos documentos.",
        "placeholder": "",
    },
    "attendance_protocol": {
        "label": "Número do protocolo",
        "input_type": "text",
        "help_text": "Protocolo de atendimento pericial, se houver.",
        "placeholder": "",
    },
    "examination_at": {
        "label": "Data e hora do exame",
        "input_type": "datetime-local",
        "help_text": "Momento do exame pericial no local ou na unidade.",
        "placeholder": "",
    },
    "photography": {
        "label": "Fotógrafo",
        "input_type": "text",
        "help_text": "Profissional responsável pela fotografia pericial.",
        "placeholder": "",
    },
    "scanning_3d": {
        "label": "Escaneamento 3D",
        "input_type": "text",
        "help_text": "Responsável ou referência do escaneamento 3D.",
        "placeholder": "",
    },
    "sketch": {
        "label": "Croqui",
        "input_type": "text",
        "help_text": "Responsável ou referência do croqui pericial.",
        "placeholder": "",
    },
}


def empty_bootstrap_payload(*, supplementary_prompt: str = "") -> dict[str, Any]:
    """Monta payload inicial de bootstrap com metadados vazios."""
    metadata = CaseMetadata(
        supplementary_prompt=supplementary_prompt.strip(),
        report_year=date.today().year,
    )
    return {
        "state": STATE_SHELL_CREATED,
        "workflow": GENERIC_WORKFLOW.slug,
        "metadata": case_metadata_to_form_dict(metadata),
        "nodes": {},
        "pending_prompts": compute_pending_prompts(metadata),
        "skipped_prompts": [],
    }


def get_bootstrap_meta(page_layout: dict[str, Any] | None) -> dict[str, Any] | None:
    """Retorna metadados de bootstrap ou ``None`` quando ausentes."""
    if not isinstance(page_layout, dict):
        return None
    meta = page_layout.get(REPORTLINE_META_KEY, {})
    if not isinstance(meta, dict):
        return None
    bootstrap = meta.get(BOOTSTRAP_META_KEY)
    return deepcopy(bootstrap) if isinstance(bootstrap, dict) else None


def attach_bootstrap_meta(page_layout: dict[str, Any], bootstrap: dict[str, Any]) -> dict[str, Any]:
    """Anexa ou substitui metadados de bootstrap no layout do laudo."""
    merged = deepcopy(page_layout)
    meta = dict(merged.get(REPORTLINE_META_KEY, {}))
    meta[BOOTSTRAP_META_KEY] = deepcopy(bootstrap)
    merged[REPORTLINE_META_KEY] = meta
    return merged


def is_forensic_bootstrap_pending(report: Report) -> bool:
    """Indica se o laudo ainda está em bootstrap interativo incompleto."""
    if not is_forensic_report(report):
        return False
    bootstrap = get_bootstrap_meta(report.page_layout)
    if not bootstrap:
        return False
    return bootstrap.get("state") != STATE_READY


def bootstrap_state(report: Report) -> str | None:
    """Retorna estado atual do bootstrap ou ``None``."""
    bootstrap = get_bootstrap_meta(report.page_layout)
    if not bootstrap:
        return None
    state = bootstrap.get("state")
    return state if isinstance(state, str) else None


def metadata_from_bootstrap(page_layout: dict[str, Any] | None) -> CaseMetadata:
    """Reconstrói ``CaseMetadata`` a partir do JSON persistido no bootstrap."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("metadata", {})
    if not isinstance(raw, dict):
        raw = {}
    query = QueryDict(mutable=True)
    for key, value in raw.items():
        if value is None:
            continue
        query[key] = str(value)
    return case_metadata_from_post(query)


def field_coverage_from_bootstrap(page_layout: dict[str, Any] | None) -> dict[str, str]:
    """Retorna mapa de cobertura inferida pela IA persistido no bootstrap."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("field_coverage", {})
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def is_scene_continuation_completed(page_layout: dict[str, Any] | None) -> bool:
    """Indica se a etapa de continuação de exame de local já foi concluída."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    return bool(bootstrap.get("scene_continuation_completed"))


def resolve_state_after_analyze(
    report: Report,
    metadata: CaseMetadata,
    *,
    skipped: set[str] | None = None,
    field_coverage: dict[str, str] | None = None,
) -> str:
    """Define estado do bootstrap após análise documental."""
    if not is_scene_continuation_completed(report.page_layout):
        return STATE_COLLECTING_SCENE_CONTINUATION
    pending = compute_pending_prompts(
        metadata,
        skipped=skipped,
        field_coverage=field_coverage,
    )
    return STATE_COLLECTING_PROMPTS if pending else STATE_ANALYZED


def save_bootstrap_after_analyze(
    report: Report,
    metadata: CaseMetadata,
    *,
    field_coverage: dict[str, str] | None = None,
) -> Report:
    """Persiste metadados inferidos e abre coleta de prompts quando necessário."""
    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    coverage = field_coverage or {}
    pending = compute_pending_prompts(metadata, skipped=skipped, field_coverage=coverage)
    state = resolve_state_after_analyze(
        report,
        metadata,
        skipped=skipped,
        field_coverage=coverage,
    )
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["state"] = state
    bootstrap["pending_prompts"] = pending
    bootstrap["skipped_prompts"] = sorted(skipped)
    bootstrap["field_coverage"] = coverage
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def save_bootstrap_metadata(report: Report, metadata: CaseMetadata, *, state: str) -> Report:
    """Atualiza metadados e estado de bootstrap no laudo."""
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["state"] = state
    bootstrap["pending_prompts"] = compute_pending_prompts(metadata, skipped=skipped)
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def save_bootstrap_nodes(report: Report, nodes: dict[str, str], *, state: str) -> Report:
    """Persiste mapa de nós seminais e estado do bootstrap."""
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    bootstrap["nodes"] = dict(nodes)
    bootstrap["state"] = state
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def compute_pending_prompts(
    metadata: CaseMetadata,
    skipped: set[str] | None = None,
    *,
    field_coverage: dict[str, str] | None = None,
) -> list[str]:
    """Lista campos inferidos pela IA ainda vazios após análise ou resposta do perito."""
    skipped_fields = skipped or set()
    coverage = field_coverage or {}
    pending: list[str] = []
    for field_name, _label in CRITICAL_PROMPT_FIELDS:
        if field_name not in ALL_PROMPT_FIELD_NAMES:
            continue
        if field_name in skipped_fields:
            continue
        if not is_prompt_field_value_empty(metadata, field_name):
            continue
        if field_name in DATETIME_PROMPT_FIELD_NAMES and coverage.get(field_name) == "date_only":
            continue
        pending.append(field_name)
    return pending


def skipped_prompts_from_bootstrap(page_layout: dict[str, Any] | None) -> set[str]:
    """Retorna campos marcados como pulados pelo perito."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("skipped_prompts", [])
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


def resolve_bootstrap_state(metadata: CaseMetadata, *, skipped: set[str] | None = None) -> str:
    """Define estado do bootstrap após montagem ou atualização de metadados."""
    if compute_pending_prompts(metadata, skipped=skipped):
        return STATE_PROMPTING
    return STATE_READY


def resolve_bootstrap_state_after_prompt_update(
    report: Report,
    metadata: CaseMetadata,
    *,
    skipped: set[str] | None = None,
) -> str:
    """Recalcula estado após resposta ou skip de prompt."""
    skipped_set = skipped if skipped is not None else skipped_prompts_from_bootstrap(report.page_layout)
    coverage = field_coverage_from_bootstrap(report.page_layout)
    pending = compute_pending_prompts(
        metadata,
        skipped=skipped_set,
        field_coverage=coverage,
    )
    current = bootstrap_state(report)
    if current == STATE_COLLECTING_PROMPTS:
        return STATE_ANALYZED if not pending else STATE_COLLECTING_PROMPTS
    if pending:
        return STATE_PROMPTING
    return STATE_READY


def prompt_field_descriptor(field_name: str) -> dict[str, str] | None:
    """Retorna rótulo, tipo de input e valor padrão para prompt inline do campo."""
    config = PROMPT_FIELD_CONFIG.get(field_name)
    if not config:
        return None
    descriptor = dict(config)
    default_value = default_prompt_value(field_name)
    if default_value:
        descriptor["default_value"] = default_value
    return descriptor


def next_pending_prompt(page_layout: dict[str, Any] | None) -> dict[str, str] | None:
    """Retorna descritor do próximo prompt pendente, se houver."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    pending = bootstrap.get("pending_prompts", [])
    if not isinstance(pending, list) or not pending:
        return None
    field_name = str(pending[0])
    descriptor = prompt_field_descriptor(field_name)
    if descriptor is None:
        return None
    return {"field": field_name, **descriptor}


def mark_prompt_skipped(report: Report, field_name: str) -> Report:
    """Registra campo como pulado e recalcula fila de prompts."""
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    skipped = set(skipped_prompts_from_bootstrap(report.page_layout))
    skipped.add(field_name)
    bootstrap["skipped_prompts"] = sorted(skipped)

    metadata = metadata_from_bootstrap(report.page_layout)
    coverage = field_coverage_from_bootstrap(report.page_layout)
    bootstrap["pending_prompts"] = compute_pending_prompts(
        metadata,
        skipped=skipped,
        field_coverage=coverage,
    )
    bootstrap["state"] = resolve_bootstrap_state_after_prompt_update(
        report,
        metadata,
        skipped=skipped,
    )
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def save_bootstrap_after_metadata_update(
    report: Report,
    metadata: CaseMetadata,
) -> Report:
    """Persiste metadados atualizados e recalcula prompts/estado."""
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    coverage = field_coverage_from_bootstrap(report.page_layout)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["pending_prompts"] = compute_pending_prompts(
        metadata,
        skipped=skipped,
        field_coverage=coverage,
    )
    bootstrap["state"] = resolve_bootstrap_state_after_prompt_update(
        report,
        metadata,
        skipped=skipped,
    )
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def set_bootstrap_state(report: Report, state: str) -> Report:
    """Atualiza apenas o estado do bootstrap no laudo."""
    bootstrap = get_bootstrap_meta(report.page_layout) or empty_bootstrap_payload()
    bootstrap["state"] = state
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


def forensic_bootstrap_editor_config(report: Report) -> dict[str, Any] | None:
    """Monta configuração JSON do bootstrap para o editor de laudos."""
    if not is_forensic_bootstrap_pending(report):
        return None

    from django.urls import reverse

    state = bootstrap_state(report)
    config: dict[str, Any] = {
        "state": state,
        "reportId": str(report.pk),
        "analyzeUrl": reverse("reports:forensic_bootstrap_analyze", kwargs={"pk": report.pk}),
        "sceneContinuationUrl": reverse(
            "reports:forensic_bootstrap_scene_continuation",
            kwargs={"pk": report.pk},
        ),
        "buildUrl": reverse("reports:forensic_bootstrap_build", kwargs={"pk": report.pk}),
        "buildStepUrl": reverse("reports:forensic_bootstrap_build_step", kwargs={"pk": report.pk}),
        "statusUrl": reverse("reports:forensic_bootstrap_status", kwargs={"pk": report.pk}),
        "finalizeUrl": reverse(
            "reports:forensic_bootstrap_finalize",
            kwargs={"pk": report.pk},
        ),
    }

    if state in (STATE_COLLECTING_SCENE_CONTINUATION, STATE_COLLECTING_PROMPTS, STATE_PROMPTING):
        metadata = metadata_from_bootstrap(report.page_layout)
        config["metadata"] = case_metadata_to_form_dict(metadata)
        if state == STATE_COLLECTING_SCENE_CONTINUATION:
            bootstrap = get_bootstrap_meta(report.page_layout) or {}
            config["examCategory"] = bootstrap.get("exam_category") or metadata.exam_category
        if state in (STATE_COLLECTING_PROMPTS, STATE_PROMPTING):
            config.update(forensic_bootstrap_prompt_config(report))

    return config


def forensic_bootstrap_prompt_config(report: Report) -> dict[str, Any]:
    """Monta configuração JSON dos prompts inline após montagem do laudo."""
    from django.urls import reverse

    metadata = metadata_from_bootstrap(report.page_layout)
    return {
        "finalizeUrl": reverse(
            "reports:forensic_bootstrap_finalize",
            kwargs={"pk": report.pk},
        ),
        "metadata": case_metadata_to_form_dict(metadata),
        "pendingPrompts": pending_prompt_catalog(report.page_layout),
    }


def pending_prompt_catalog(page_layout: dict[str, Any] | None) -> list[dict[str, str]]:
    """Lista descritores de todos os prompts pendentes para o frontend."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    pending = bootstrap.get("pending_prompts", [])
    if not isinstance(pending, list):
        pending = compute_pending_prompts(metadata_from_bootstrap(page_layout))
    catalog: list[dict[str, str]] = []
    for field_name in pending:
        descriptor = prompt_field_descriptor(str(field_name))
        if descriptor is None:
            continue
        catalog.append({"field": str(field_name), **descriptor})
    return catalog


def bootstrap_status_payload(report: Report) -> dict[str, Any]:
    """Serializa status do bootstrap para respostas JSON."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    metadata = metadata_from_bootstrap(report.page_layout)
    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    pending = bootstrap.get("pending_prompts")
    if not isinstance(pending, list):
        pending = compute_pending_prompts(metadata, skipped=skipped)
    payload = {
        "state": bootstrap.get("state", STATE_READY),
        "metadata": case_metadata_to_form_dict(metadata),
        "pending_prompts": pending,
        "nodes": bootstrap.get("nodes", {}),
        "next_prompt": next_pending_prompt(report.page_layout),
    }
    return payload
