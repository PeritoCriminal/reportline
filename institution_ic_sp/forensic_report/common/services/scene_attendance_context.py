# reportline/institution_ic_sp/forensic_report/common/services/scene_attendance_context.py
"""
Dados estruturados do contexto de atendimento pericial no local.

Complementam a inferência de texto da seção Contexto de Atendimento e podem
ser extraídos da minuta/requisição ou informados pelo perito via prompts inline.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

LOCATION_PRESERVED_YES = "yes"
LOCATION_PRESERVED_NO = "no"
LOCATION_PRESERVED_PARTIALLY = "partially"

LOCATION_PRESERVED_VALUES = frozenset(
    {
        LOCATION_PRESERVED_YES,
        LOCATION_PRESERVED_NO,
        LOCATION_PRESERVED_PARTIALLY,
    }
)

YES_NO_VALUES = frozenset({"yes", "no"})

EXTENSION_KEY_MAP: dict[str, str] = {
    "scene_location_preserved": "location_preserved",
    "scene_police_authority_present": "police_authority_present",
    "scene_investigation_team_present": "investigation_team_present",
    "scene_access_granted_by": "access_granted_by",
    "scene_informant_provided_info": "informant_provided_info",
    "scene_informant_briefing": "informant_briefing",
}


@dataclass
class SceneAttendanceContext:
    """Circunstâncias objetivas do atendimento pericial no local examinado."""

    location_preserved: str = ""
    police_authority_present: str = ""
    investigation_team_present: str = ""
    access_granted_by: str = ""
    informant_provided_info: str = ""
    informant_briefing: str = ""


def _normalize_yes_no(value: Any) -> str:
    """Normaliza respostas sim/não para valores canônicos."""
    cleaned = str(value or "").strip().lower()
    if cleaned in {"sim", "s", "yes", "y", "true", "1"}:
        return "yes"
    if cleaned in {"nao", "não", "n", "no", "false", "0"}:
        return "no"
    return cleaned if cleaned in YES_NO_VALUES else ""


def _normalize_location_preserved(value: Any) -> str:
    """Normaliza preservação do local para valores canônicos."""
    cleaned = str(value or "").strip().lower()
    if cleaned in {"sim", "s", "yes", "y", "true", "1", "preservado"}:
        return LOCATION_PRESERVED_YES
    if cleaned in {"nao", "não", "n", "no", "false", "0", "nao_preservado", "não preservado"}:
        return LOCATION_PRESERVED_NO
    if cleaned in {
        "parcial",
        "parcialmente",
        "partial",
        "partially",
        "parcialmente preservado",
    }:
        return LOCATION_PRESERVED_PARTIALLY
    return cleaned if cleaned in LOCATION_PRESERVED_VALUES else ""


def normalize_scene_attendance_context(raw: dict[str, Any] | None) -> SceneAttendanceContext:
    """Valida e normaliza payload bruto do contexto de atendimento."""
    if not isinstance(raw, dict):
        return SceneAttendanceContext()

    return SceneAttendanceContext(
        location_preserved=_normalize_location_preserved(raw.get("location_preserved")),
        police_authority_present=_normalize_yes_no(raw.get("police_authority_present")),
        investigation_team_present=_normalize_yes_no(raw.get("investigation_team_present")),
        access_granted_by=str(raw.get("access_granted_by", "")).strip(),
        informant_provided_info=_normalize_yes_no(raw.get("informant_provided_info")),
        informant_briefing=str(raw.get("informant_briefing", "")).strip(),
    )


def scene_attendance_context_from_extensions(
    extensions: dict[str, Any] | None,
) -> SceneAttendanceContext:
    """Monta contexto de atendimento a partir de chaves em ``extensions``."""
    if not isinstance(extensions, dict):
        return SceneAttendanceContext()

    mapped: dict[str, Any] = {}
    for extension_key, field_name in EXTENSION_KEY_MAP.items():
        if extension_key in extensions:
            mapped[field_name] = extensions.get(extension_key)
    return normalize_scene_attendance_context(mapped)


def scene_attendance_context_to_payload(context: SceneAttendanceContext) -> dict[str, str]:
    """Serializa contexto de atendimento para JSON do bootstrap/dossier."""
    return {field.name: str(getattr(context, field.name) or "") for field in fields(context)}


def scene_attendance_context_from_bootstrap(page_layout: dict | None) -> SceneAttendanceContext:
    """Recupera contexto de atendimento persistido no bootstrap."""
    from institution_ic_sp.forensic_report.services.forensic_bootstrap import get_bootstrap_meta

    bootstrap = get_bootstrap_meta(page_layout) or {}
    raw = bootstrap.get("scene_attendance_context", {})
    if not isinstance(raw, dict):
        return SceneAttendanceContext()
    return normalize_scene_attendance_context(raw)


def attendance_context_display_labels(context: SceneAttendanceContext) -> dict[str, str]:
    """Traduz valores canônicos para rótulos em português usados na IA."""
    preserved_labels = {
        LOCATION_PRESERVED_YES: "sim, preservado",
        LOCATION_PRESERVED_NO: "não, sem preservação",
        LOCATION_PRESERVED_PARTIALLY: "parcialmente preservado",
    }
    yes_no_labels = {"yes": "sim", "no": "não"}

    payload: dict[str, str] = {}
    if context.location_preserved:
        payload["local_preservado"] = preserved_labels.get(
            context.location_preserved,
            context.location_preserved,
        )
    if context.police_authority_present:
        payload["autoridade_policial_presente"] = yes_no_labels.get(
            context.police_authority_present,
            context.police_authority_present,
        )
    if context.investigation_team_present:
        payload["equipe_investigacao_presente"] = yes_no_labels.get(
            context.investigation_team_present,
            context.investigation_team_present,
        )
    if context.access_granted_by:
        payload["acesso_franqueado_por"] = context.access_granted_by
    if context.informant_provided_info:
        payload["informes_prestados"] = yes_no_labels.get(
            context.informant_provided_info,
            context.informant_provided_info,
        )
    if context.informant_briefing:
        payload["conteudo_dos_informes"] = context.informant_briefing
    return payload


def attendance_context_summary_for_prompt(context: SceneAttendanceContext) -> str:
    """Resume dados estruturados em texto legível para o prompt da IA."""
    labels = attendance_context_display_labels(context)
    if not labels:
        return "(nenhum dado estruturado informado)"
    lines = [f"- {key}: {value}" for key, value in labels.items()]
    return "\n".join(lines)
