# reportline/institution_ic_sp/forensic_report/services/scene_attendance_context_prompts.py
"""
Prompts inline do contexto de atendimento pericial no exame de local.

Campos podem ser inferidos da minuta/requisição ou coletados do perito no
mesmo padrão visual dos prompts administrativos do bootstrap.
"""

from __future__ import annotations

from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
    SceneAttendanceContext,
    normalize_scene_attendance_context,
    scene_attendance_context_to_payload,
)

ATTENDANCE_CONTEXT_FIELD_NAMES: tuple[str, ...] = (
    "location_preserved",
    "police_authority_present",
    "investigation_team_present",
    "access_granted_by",
    "informant_provided_info",
    "informant_briefing",
)

ATTENDANCE_CONTEXT_PROMPT_CONFIG: dict[str, dict[str, str | list[dict[str, str]]]] = {
    "location_preserved": {
        "label": "O local estava preservado?",
        "input_type": "select",
        "help_text": "Indique se o imóvel ou área encontrava-se preservada no momento do atendimento.",
        "placeholder": "",
        "choices": [
            {"value": "yes", "label": "Sim"},
            {"value": "no", "label": "Não"},
            {"value": "partially", "label": "Parcialmente"},
        ],
    },
    "police_authority_present": {
        "label": "A autoridade policial estava presente?",
        "input_type": "select",
        "help_text": "Informe se delegado, escrivão ou autoridade requisitante acompanhou o atendimento.",
        "placeholder": "",
        "choices": [
            {"value": "yes", "label": "Sim"},
            {"value": "no", "label": "Não"},
        ],
    },
    "investigation_team_present": {
        "label": "Equipe de investigação estava presente?",
        "input_type": "select",
        "help_text": "Informe se policiais, GCM ou equipe de diligências permanecia no local.",
        "placeholder": "",
        "choices": [
            {"value": "yes", "label": "Sim"},
            {"value": "no", "label": "Não"},
        ],
    },
    "access_granted_by": {
        "label": "O acesso ao local foi franqueado por",
        "input_type": "text",
        "help_text": "Nome ou qualificação breve de quem autorizou o ingresso (ex.: proprietário, síndico).",
        "placeholder": "Ex.: proprietário do imóvel",
    },
    "informant_provided_info": {
        "label": "Essa pessoa prestou informes?",
        "input_type": "select",
        "help_text": "Indique se quem franqueou o acesso ou outra pessoa presente forneceu esclarecimentos.",
        "placeholder": "",
        "choices": [
            {"value": "yes", "label": "Sim"},
            {"value": "no", "label": "Não"},
        ],
    },
    "informant_briefing": {
        "label": "Informes prestados",
        "input_type": "textarea",
        "help_text": "Resuma objetivamente os esclarecimentos recebidos, sem narrar dinâmica dos fatos.",
        "placeholder": "Ex.: informou ter constatado o imóvel fechado ao retornar da viagem.",
    },
}


def is_attendance_context_field_empty(
    context: SceneAttendanceContext,
    field_name: str,
) -> bool:
    """Indica se campo do contexto de atendimento permanece sem valor."""
    if field_name == "informant_briefing":
        if context.informant_provided_info != "yes":
            return False
        return not context.informant_briefing.strip()
    return not str(getattr(context, field_name, "") or "").strip()


def compute_pending_attendance_context_prompts(
    context: SceneAttendanceContext,
    *,
    skipped: set[str] | None = None,
) -> list[str]:
    """Lista campos do contexto de atendimento ainda pendentes de informação."""
    skipped_fields = skipped or set()
    pending: list[str] = []
    for field_name in ATTENDANCE_CONTEXT_FIELD_NAMES:
        if field_name in skipped_fields:
            continue
        if field_name in ("informant_provided_info", "informant_briefing"):
            if not context.access_granted_by.strip():
                continue
        if field_name == "informant_briefing" and context.informant_provided_info != "yes":
            continue
        if not is_attendance_context_field_empty(context, field_name):
            continue
        pending.append(field_name)
    return pending


def attendance_context_prompt_descriptor(
    field_name: str,
    *,
    context: SceneAttendanceContext | None = None,
) -> dict[str, object] | None:
    """Retorna descritor de prompt inline para um campo do contexto de atendimento."""
    config = ATTENDANCE_CONTEXT_PROMPT_CONFIG.get(field_name)
    if not config:
        return None

    descriptor: dict[str, object] = {"field": field_name, **config}
    if field_name == "informant_provided_info" and context and context.access_granted_by:
        descriptor["help_text"] = (
            f"Indique se {context.access_granted_by} prestou esclarecimentos sobre o atendimento."
        )
    if field_name == "informant_briefing" and context and context.access_granted_by:
        descriptor["label"] = f"Informes prestados por {context.access_granted_by}"
    return descriptor


def pending_attendance_context_prompt_catalog(
    context: SceneAttendanceContext,
    *,
    skipped: set[str] | None = None,
) -> list[dict[str, object]]:
    """Monta catálogo de prompts pendentes para o frontend."""
    catalog: list[dict[str, object]] = []
    for field_name in compute_pending_attendance_context_prompts(context, skipped=skipped):
        descriptor = attendance_context_prompt_descriptor(field_name, context=context)
        if descriptor is None:
            continue
        catalog.append(descriptor)
    return catalog


def apply_attendance_context_answers(
    context: SceneAttendanceContext,
    answers: dict[str, str],
) -> SceneAttendanceContext:
    """Aplica respostas do perito ao contexto de atendimento."""
    payload = normalize_scene_attendance_context(scene_attendance_context_to_payload(context))
    raw = scene_attendance_context_to_payload(payload)
    for field_name, value in answers.items():
        if field_name not in ATTENDANCE_CONTEXT_FIELD_NAMES:
            continue
        raw[field_name] = str(value).strip()
    updated = normalize_scene_attendance_context(raw)
    if updated.informant_provided_info != "yes":
        updated.informant_briefing = ""
    return updated

