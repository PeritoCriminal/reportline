"""
Montagem incremental do corpo padronizado de laudo pericial.

Permite criar blocos passo a passo para exibição progressiva no editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.common.services.scene_location import (
    SceneLocationData,
    scene_location_for_report,
    scene_location_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.scene_examination_content import (
    scene_examination_content_from_bootstrap,
    should_build_scene_examination_section,
)
from institution_ic_sp.forensic_report.services.scene_location_table import (
    build_scene_location_table_content,
)
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    STATE_COLLECTING_SCENE_CONTINUATION,
    STATE_READY,
    attach_bootstrap_meta,
    compute_pending_prompts,
    get_bootstrap_meta,
    is_scene_continuation_completed,
    metadata_from_bootstrap,
    resolve_bootstrap_state,
    resolve_state_after_initial_build,
    set_bootstrap_state,
    skipped_prompts_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.forensic_report_body_builder import (
    CLOSING_DIGITAL_ARCHIVE_NOTICE,
    CLOSING_PHRASE,
    _create_report_node,
    _examiner_signature_text,
    _wrap_italic_text,
    _wrap_preamble_text,
    clear_report_body_nodes,
    update_header_report_number,
)
from institution_ic_sp.forensic_report.services.preamble import build_preamble_paragraph
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportBlockType, ReportNode
from reports.models.report_block import ReportBlockLineSpacing
from reports.services.report_block_indent import MAX_INDENT_LEVEL
from reports.services.report_tree import insert_sibling_after

BUILD_PHASE_INITIAL = "initial"
BUILD_PHASE_SCENE = "scene"

INITIAL_BUILD_STEP_IDS: tuple[str, ...] = (
    "main_title",
    "preamble",
    "objective_heading",
    "objective_body",
    "requisition_heading",
    "requisition_list",
    "attendance_heading",
    "attendance_list",
    "body_spacer",
    "closing_phrase",
    "closing_notice",
    "signature",
    "finalize",
)

SCENE_BUILD_STEP_IDS: tuple[str, ...] = (
    "scene_section_heading",
    "scene_location_heading",
    "scene_location_table",
    "scene_context_heading",
    "scene_context_body",
    "scene_characteristics_heading",
    "scene_characteristics_body",
)

BUILD_STEP_IDS: tuple[str, ...] = INITIAL_BUILD_STEP_IDS + SCENE_BUILD_STEP_IDS

INTERACTIVE_BUILD_STEP_IDS: frozenset[str] = frozenset(
    {
        "main_title",
        "preamble",
        "objective_heading",
        "objective_body",
        "requisition_heading",
        "requisition_list",
        "attendance_heading",
        "attendance_list",
        "scene_section_heading",
        "scene_location_heading",
        "scene_location_table",
        "scene_context_heading",
        "scene_context_body",
        "scene_characteristics_heading",
        "scene_characteristics_body",
    }
)

INITIAL_INTERACTIVE_BUILD_STEP_IDS = INTERACTIVE_BUILD_STEP_IDS - frozenset(
    step_id for step_id in SCENE_BUILD_STEP_IDS
)

SCENE_INTERACTIVE_BUILD_STEP_IDS = frozenset(SCENE_BUILD_STEP_IDS)

SILENT_BUILD_STEP_IDS: frozenset[str] = frozenset(
    {
        "body_spacer",
        "closing_phrase",
        "closing_notice",
        "signature",
        "finalize",
    }
)

BUILD_STEP_LABELS: dict[str, str] = {
    "main_title": "Inserindo título do laudo…",
    "preamble": "Escrevendo preâmbulo…",
    "objective_heading": "Adicionando seção de objetivo…",
    "objective_body": "Registrando objetivo do exame…",
    "requisition_heading": "Abrindo dados da requisição…",
    "requisition_list": "Listando dados da requisição…",
    "attendance_heading": "Abrindo dados do atendimento…",
    "attendance_list": "Listando dados do atendimento…",
    "scene_section_heading": "Abrindo descrição do local…",
    "scene_location_heading": "Registrando localização…",
    "scene_location_table": "Inserindo mapa e QR code…",
    "scene_context_heading": "Abrindo contexto de atendimento…",
    "scene_context_body": "Descrevendo contexto de atendimento…",
    "scene_characteristics_heading": "Abrindo características do local…",
    "scene_characteristics_body": "Descrevendo características do local…",
    "body_spacer": "Organizando fechamento…",
    "closing_phrase": "Inserindo encerramento…",
    "closing_notice": "Registrando arquivamento digital…",
    "signature": "Posicionando assinatura…",
    "finalize": "Finalizando laudo…",
}


def _build_steps_for_phase(phase: str) -> tuple[str, ...]:
    """Retorna sequência de passos conforme fase de montagem."""
    if phase == BUILD_PHASE_SCENE:
        return SCENE_BUILD_STEP_IDS
    return INITIAL_BUILD_STEP_IDS


def _interactive_steps_for_phase(phase: str) -> frozenset[str]:
    """Retorna passos animados conforme fase de montagem."""
    if phase == BUILD_PHASE_SCENE:
        return SCENE_INTERACTIVE_BUILD_STEP_IDS
    return INITIAL_INTERACTIVE_BUILD_STEP_IDS


def _resolve_scene_insert_anchor(node_registry: dict[str, str]) -> str:
    """Determina nó após o qual a seção de local deve ser inserida."""
    for key in (
        "attendance_list",
        "attendance_heading",
        "requisition_list",
        "requisition_heading",
        "objective_body",
        "objective_heading",
        "preamble",
        "main_title",
    ):
        node_id = node_registry.get(key)
        if node_id:
            return node_id
    raise ValueError("Não foi possível determinar ponto de inserção da seção de local.")


def step_should_run(
    step_id: str,
    metadata: CaseMetadata,
    *,
    page_layout: dict | None = None,
    phase: str = BUILD_PHASE_INITIAL,
) -> bool:
    """Indica se o passo produz conteúdo a partir dos metadados inferidos pela IA."""
    if phase == BUILD_PHASE_INITIAL and step_id.startswith("scene_"):
        return False
    if phase == BUILD_PHASE_SCENE and not step_id.startswith("scene_"):
        return False
    if step_id in SILENT_BUILD_STEP_IDS:
        return True
    if step_id in {"main_title", "preamble"}:
        return True
    if step_id in {"objective_heading", "objective_body"}:
        return bool(metadata.exam_objective.strip())
    if step_id in {"requisition_heading", "requisition_list"}:
        return bool(metadata.requisition_list_items())
    if step_id in {"attendance_heading", "attendance_list"}:
        return bool(metadata.attendance_list_items())
    if step_id.startswith("scene_"):
        if not should_build_scene_examination_section(metadata, page_layout):
            return False
        content = scene_examination_content_from_bootstrap(page_layout)
        location = scene_location_from_bootstrap(page_layout)
        if step_id == "scene_section_heading":
            return True
        if step_id in {"scene_location_heading", "scene_location_table"}:
            return location.is_present
        if step_id == "scene_context_heading":
            return bool(content.get("attendance_context_paragraph"))
        if step_id == "scene_context_body":
            return bool(content.get("attendance_context_paragraph"))
        if step_id == "scene_characteristics_heading":
            return bool(content.get("characteristics_paragraph"))
        if step_id == "scene_characteristics_body":
            return bool(content.get("characteristics_paragraph"))
        return False
    return True


def count_interactive_build_steps(
    metadata: CaseMetadata,
    *,
    page_layout: dict | None = None,
    phase: str = BUILD_PHASE_INITIAL,
) -> int:
    """Conta passos animados que serão exibidos na montagem incremental."""
    interactive_steps = _interactive_steps_for_phase(phase)
    build_steps = _build_steps_for_phase(phase)
    return sum(
        1
        for step_id in build_steps
        if step_id in interactive_steps
        and step_should_run(step_id, metadata, page_layout=page_layout, phase=phase)
    )


def count_completed_interactive_steps(
    metadata: CaseMetadata,
    step_index: int,
    *,
    page_layout: dict | None = None,
    phase: str = BUILD_PHASE_INITIAL,
) -> int:
    """Conta passos interativos já concluídos até ``step_index``."""
    interactive_steps = _interactive_steps_for_phase(phase)
    build_steps = _build_steps_for_phase(phase)
    completed = 0
    for index, step_id in enumerate(build_steps):
        if index >= step_index:
            break
        if step_id in interactive_steps and step_should_run(
            step_id,
            metadata,
            page_layout=page_layout,
            phase=phase,
        ):
            completed += 1
    return completed


def is_interactive_build_step(step_id: str | None) -> bool:
    """Indica se o passo entra na animação visível do editor."""
    return bool(step_id and step_id in INTERACTIVE_BUILD_STEP_IDS)


@dataclass
class SceneBuildContext:
    """Estado mutável da inserção mid-tree da seção de exame de local."""

    report: Report
    examiner: ForensicExaminerSP
    metadata: CaseMetadata
    institution: Institution
    anchor_node: ReportNode
    node_registry: dict[str, str] = field(default_factory=dict)


def _context_from_scene_progress(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
    institution: Institution,
    progress: dict,
) -> SceneBuildContext:
    """Reconstrói contexto de inserção da seção de local."""
    nodes = progress.get("nodes", {})
    node_registry = dict(nodes) if isinstance(nodes, dict) else {}
    anchor_id = progress.get("scene_anchor_node_id") or progress.get("scene_insert_after_node_id")
    if not anchor_id:
        raise ValueError("Ponto de inserção da seção de local não definido.")
    anchor_node = ReportNode.objects.select_related("block").get(
        pk=anchor_id,
        report=report,
    )
    return SceneBuildContext(
        report=report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        anchor_node=anchor_node,
        node_registry=node_registry,
    )


def _insert_scene_report_node(
    ctx: SceneBuildContext,
    *,
    block_type: str,
    content: dict,
    title_level: int = 0,
    text_align: str | None = None,
    first_line_indent: bool | None = None,
) -> ReportNode:
    """Insere bloco da seção de local após o nó âncora atual."""
    node = insert_sibling_after(
        ctx.report,
        ctx.anchor_node,
        block_type=block_type,
        content=content,
        title_level=title_level,
        first_line_indent=first_line_indent,
    )
    if text_align is not None:
        block = node.block
        block.text_align = text_align
        block.save(update_fields=["text_align", "updated_at"])
    ctx.anchor_node = node
    return node


def _run_scene_build_step(step_id: str, ctx: SceneBuildContext) -> list[ReportNode]:
    """Executa passo de montagem inserindo blocos antes do fechamento."""
    scene_content = scene_examination_content_from_bootstrap(ctx.report.page_layout)
    scene_location = scene_location_for_report(ctx.report)

    if step_id == "scene_section_heading":
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.HEADING,
            content={"text": "Descrição e Exame do Local"},
            title_level=0,
        )
        ctx.node_registry["scene_section_heading"] = str(node.pk)
        return [node]

    if step_id == "scene_location_heading":
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.HEADING,
            content={"text": "Localização:"},
            title_level=1,
        )
        ctx.node_registry["scene_location_heading"] = str(node.pk)
        return [node]

    if step_id == "scene_location_table":
        table_content = build_scene_location_table_content(ctx.report, scene_location)
        if not table_content:
            return []
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.TABLE,
            content=table_content,
        )
        ctx.node_registry["scene_location_table"] = str(node.pk)
        return [node]

    if step_id == "scene_context_heading":
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.HEADING,
            content={"text": "Contexto de atendimento"},
            title_level=1,
        )
        ctx.node_registry["scene_context_heading"] = str(node.pk)
        return [node]

    if step_id == "scene_context_body":
        paragraph = scene_content.get("attendance_context_paragraph", "")
        if not paragraph:
            return []
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": paragraph},
        )
        ctx.node_registry["scene_context_body"] = str(node.pk)
        return [node]

    if step_id == "scene_characteristics_heading":
        heading = scene_content.get("characteristics_heading") or "Características do Local"
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.HEADING,
            content={"text": heading},
            title_level=1,
        )
        ctx.node_registry["scene_characteristics_heading"] = str(node.pk)
        return [node]

    if step_id == "scene_characteristics_body":
        paragraph = scene_content.get("characteristics_paragraph", "")
        if not paragraph:
            return []
        node = _insert_scene_report_node(
            ctx,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": paragraph},
        )
        ctx.node_registry["scene_characteristics_body"] = str(node.pk)
        return [node]

    raise ValueError(f"Passo de montagem de local desconhecido: {step_id}")


def start_scene_build_phase(report: Report) -> Report:
    """Prepara montagem incremental da seção de local após continuação de exame."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    anchor_id = bootstrap.get("scene_insert_after_node_id")
    if not anchor_id:
        raise ValueError("Montagem inicial do laudo deve ser concluída antes da seção de local.")

    bootstrap["build_progress"] = {
        "phase": BUILD_PHASE_SCENE,
        "step_index": 0,
        "nodes": dict(bootstrap.get("nodes") or {}),
        "scene_insert_after_node_id": anchor_id,
        "scene_anchor_node_id": anchor_id,
    }
    bootstrap["state"] = STATE_BUILDING
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report


@dataclass
class ForensicBodyBuildContext:
    """Estado mutável compartilhado entre passos de montagem do laudo."""

    report: Report
    examiner: ForensicExaminerSP
    metadata: CaseMetadata
    institution: Institution
    position: int = 1
    node_registry: dict[str, str] = field(default_factory=dict)


def _get_build_progress(page_layout: dict) -> dict | None:
    """Retorna progresso incremental persistido no bootstrap."""
    bootstrap = get_bootstrap_meta(page_layout) or {}
    progress = bootstrap.get("build_progress")
    return dict(progress) if isinstance(progress, dict) else None


def _save_build_progress(report: Report, progress: dict | None) -> None:
    """Persiste ou limpa progresso incremental no bootstrap."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    if progress is None:
        bootstrap.pop("build_progress", None)
    else:
        bootstrap["build_progress"] = progress
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)


def _context_from_progress(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
    institution: Institution,
    progress: dict,
) -> ForensicBodyBuildContext:
    """Reconstrói contexto de montagem a partir do progresso salvo."""
    nodes = progress.get("nodes", {})
    node_registry = dict(nodes) if isinstance(nodes, dict) else {}
    position_raw = progress.get("position", 1)
    try:
        position = int(position_raw)
    except (TypeError, ValueError):
        position = 1
    return ForensicBodyBuildContext(
        report=report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        position=position,
        node_registry=node_registry,
    )


def _run_build_step(step_id: str, ctx: ForensicBodyBuildContext) -> list[ReportNode]:
    """Executa um passo de montagem e retorna nós criados na etapa."""
    if step_id == "main_title":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.HEADING,
            content={"text": ctx.metadata.main_title_text},
            title_level=0,
            is_main_title=True,
        )
        ctx.node_registry["main_title"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "preamble":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={
                "text": _wrap_preamble_text(
                    build_preamble_paragraph(
                        ctx.metadata,
                        examiner=ctx.examiner,
                        institution=ctx.institution,
                    )
                )
            },
            indent_level=MAX_INDENT_LEVEL,
            first_line_indent=False,
            line_spacing=ReportBlockLineSpacing.COMPACT,
        )
        ctx.node_registry["preamble"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "objective_heading":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.HEADING,
            content={"text": "Objetivo do Exame"},
            title_level=0,
        )
        ctx.node_registry["objective_heading"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "objective_body":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": ctx.metadata.exam_objective.strip()},
        )
        ctx.node_registry["objective_body"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "requisition_heading":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.HEADING,
            content={"text": "Dados da Requisição"},
            title_level=0,
        )
        ctx.node_registry["requisition_heading"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "requisition_list":
        items = ctx.metadata.requisition_list_items()
        if not items:
            return []
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": items},
        )
        ctx.node_registry["requisition_list"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "attendance_heading":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.HEADING,
            content={"text": "Dados do Atendimento"},
            title_level=0,
        )
        ctx.node_registry["attendance_heading"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "attendance_list":
        items = ctx.metadata.attendance_list_items()
        if not items:
            return []
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.UNORDERED_LIST,
            content={"items": items},
        )
        ctx.node_registry["attendance_list"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "body_spacer":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": ""},
        )
        ctx.node_registry["body_spacer"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "closing_phrase":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": _wrap_italic_text(CLOSING_PHRASE)},
            first_line_indent=False,
        )
        ctx.node_registry["closing_phrase"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "closing_notice":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": CLOSING_DIGITAL_ARCHIVE_NOTICE},
            first_line_indent=False,
        )
        ctx.node_registry["closing_notice"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "signature":
        node = _create_report_node(
            ctx.report,
            position=ctx.position,
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": _examiner_signature_text(ctx.examiner)},
            text_align="right",
            first_line_indent=False,
        )
        ctx.node_registry["signature"] = str(node.pk)
        ctx.position += 1
        return [node]

    if step_id == "finalize":
        ctx.report.title = ctx.metadata.list_title
        ctx.report.page_layout = update_header_report_number(ctx.report.page_layout, ctx.metadata)
        ctx.report.save(update_fields=["title", "page_layout", "updated_at"])
        return []

    raise ValueError(f"Passo de montagem desconhecido: {step_id}")


def run_all_forensic_body_steps(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
    institution: Institution,
    replace_existing: bool = True,
) -> dict[str, str]:
    """Executa todos os passos de montagem de uma vez."""
    if replace_existing:
        clear_report_body_nodes(report)

    ctx = ForensicBodyBuildContext(
        report=report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
    )
    for step_id in INITIAL_BUILD_STEP_IDS:
        if step_should_run(
            step_id,
            metadata,
            page_layout=report.page_layout,
            phase=BUILD_PHASE_INITIAL,
        ):
            _run_build_step(step_id, ctx)

    if should_build_scene_examination_section(metadata, report.page_layout):
        anchor_id = _resolve_scene_insert_anchor(ctx.node_registry)
        anchor_node = ReportNode.objects.select_related("block").get(
            pk=anchor_id,
            report=report,
        )
        scene_ctx = SceneBuildContext(
            report=report,
            examiner=examiner,
            metadata=metadata,
            institution=institution,
            anchor_node=anchor_node,
            node_registry=dict(ctx.node_registry),
        )
        for step_id in SCENE_BUILD_STEP_IDS:
            if step_should_run(
                step_id,
                metadata,
                page_layout=report.page_layout,
                phase=BUILD_PHASE_SCENE,
            ):
                _run_scene_build_step(step_id, scene_ctx)
        ctx.node_registry.update(scene_ctx.node_registry)

    return ctx.node_registry


def _complete_initial_build_phase(
    report: Report,
    metadata: CaseMetadata,
    *,
    nodes: dict[str, str],
) -> str:
    """Finaliza fase administrativa e abre continuação de categoria de exame."""
    from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
        persist_initial_data_phase,
    )

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    skipped = skipped_prompts_from_bootstrap(report.page_layout)

    bootstrap["initial_build_completed"] = True
    bootstrap["nodes"] = dict(nodes)
    bootstrap["scene_insert_after_node_id"] = _resolve_scene_insert_anchor(nodes)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["pending_prompts"] = compute_pending_prompts(metadata, skipped=skipped)
    bootstrap["skipped_prompts"] = sorted(skipped)
    bootstrap["workflow"] = GENERIC_WORKFLOW.slug
    bootstrap.pop("build_progress", None)

    final_state = resolve_state_after_initial_build(report, metadata, skipped=skipped)
    bootstrap["state"] = final_state
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    persist_initial_data_phase(report, metadata)
    return final_state


def _complete_scene_build_phase(
    report: Report,
    metadata: CaseMetadata,
    *,
    nodes: dict[str, str],
) -> str:
    """Finaliza bootstrap após inserção da seção de exame de local."""
    from institution_ic_sp.forensic_report.services.forensic_report_dossier import (
        persist_property_crime_phase,
    )

    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    skipped = skipped_prompts_from_bootstrap(report.page_layout)

    bootstrap["nodes"] = dict(nodes)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["pending_prompts"] = compute_pending_prompts(metadata, skipped=skipped)
    bootstrap["skipped_prompts"] = sorted(skipped)
    bootstrap["workflow"] = GENERIC_WORKFLOW.slug
    bootstrap.pop("build_progress", None)

    final_state = resolve_bootstrap_state(metadata, skipped=skipped)
    bootstrap["state"] = final_state
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    persist_property_crime_phase(report, metadata)
    return final_state


def _complete_bootstrap_after_build(
    report: Report,
    metadata: CaseMetadata,
    *,
    nodes: dict[str, str] | None = None,
    phase: str = BUILD_PHASE_INITIAL,
) -> str:
    """Finaliza metadados do bootstrap após montagem completa do corpo."""
    resolved_nodes = dict(nodes or (get_bootstrap_meta(report.page_layout) or {}).get("nodes") or {})
    if phase == BUILD_PHASE_SCENE:
        return _complete_scene_build_phase(report, metadata, nodes=resolved_nodes)
    return _complete_initial_build_phase(report, metadata, nodes=resolved_nodes)


@transaction.atomic
def advance_forensic_body_build_step(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
) -> tuple[list[ReportNode], bool, str, str | None, str]:
    """
    Avança um passo na montagem incremental do laudo.

    Retorna nós criados, conclusão, estado final do bootstrap, rótulo do passo
    e fase de montagem ativa.
    """
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    metadata = metadata_from_bootstrap(report.page_layout)
    progress = _get_build_progress(report.page_layout)
    phase = BUILD_PHASE_INITIAL
    if progress:
        phase = str(progress.get("phase") or BUILD_PHASE_INITIAL)
    build_steps = _build_steps_for_phase(phase)
    step_index = int(progress.get("step_index", 0)) if progress else 0

    if progress is None:
        clear_report_body_nodes(report)
        set_bootstrap_state(report, STATE_BUILDING)
        progress = {
            "phase": BUILD_PHASE_INITIAL,
            "step_index": 0,
            "position": 1,
            "nodes": {},
        }
        phase = BUILD_PHASE_INITIAL
        build_steps = INITIAL_BUILD_STEP_IDS

    if step_index >= len(build_steps):
        final_state = _complete_bootstrap_after_build(
            report,
            metadata,
            nodes=progress.get("nodes", {}),
            phase=phase,
        )
        _save_build_progress(report, None)
        report.save(update_fields=["page_layout", "updated_at"])
        return [], True, final_state, None, phase

    step_id: str | None = None
    created_nodes: list[ReportNode] = []

    if phase == BUILD_PHASE_SCENE:
        scene_ctx = _context_from_scene_progress(
            report,
            examiner=examiner,
            metadata=metadata,
            institution=institution,
            progress=progress,
        )
        while step_index < len(build_steps):
            candidate = build_steps[step_index]
            step_index += 1
            if not step_should_run(
                candidate,
                metadata,
                page_layout=report.page_layout,
                phase=phase,
            ):
                continue
            step_id = candidate
            created_nodes = _run_scene_build_step(step_id, scene_ctx)
            progress["scene_anchor_node_id"] = str(scene_ctx.anchor_node.pk)
            progress["nodes"] = scene_ctx.node_registry
            break

        if step_id is None:
            final_state = _complete_bootstrap_after_build(
                report,
                metadata,
                nodes=scene_ctx.node_registry,
                phase=phase,
            )
            _save_build_progress(report, None)
            report.save(update_fields=["page_layout", "updated_at"])
            return [], True, final_state, None, phase
    else:
        ctx = _context_from_progress(
            report,
            examiner=examiner,
            metadata=metadata,
            institution=institution,
            progress=progress,
        )
        while step_index < len(build_steps):
            candidate = build_steps[step_index]
            step_index += 1
            if not step_should_run(
                candidate,
                metadata,
                page_layout=report.page_layout,
                phase=phase,
            ):
                continue
            step_id = candidate
            created_nodes = _run_build_step(step_id, ctx)
            progress["nodes"] = ctx.node_registry
            progress["position"] = ctx.position
            break

        if step_id is None:
            final_state = _complete_bootstrap_after_build(
                report,
                metadata,
                nodes=ctx.node_registry,
                phase=phase,
            )
            _save_build_progress(report, None)
            report.save(update_fields=["page_layout", "updated_at"])
            return [], True, final_state, None, phase

    progress["step_index"] = step_index
    _save_build_progress(report, progress)

    done = progress["step_index"] >= len(build_steps)
    final_state = STATE_BUILDING
    if done:
        node_registry = progress.get("nodes", {})
        final_state = _complete_bootstrap_after_build(
            report,
            metadata,
            nodes=node_registry if isinstance(node_registry, dict) else {},
            phase=phase,
        )
        _save_build_progress(report, None)

    report.save(update_fields=["page_layout", "updated_at"])
    return created_nodes, done, final_state, step_id, phase
