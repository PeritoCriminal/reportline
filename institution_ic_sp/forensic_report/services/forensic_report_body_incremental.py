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
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    STATE_BUILDING,
    attach_bootstrap_meta,
    compute_pending_prompts,
    get_bootstrap_meta,
    metadata_from_bootstrap,
    resolve_bootstrap_state,
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

BUILD_STEP_IDS: tuple[str, ...] = (
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

BUILD_STEP_LABELS: dict[str, str] = {
    "main_title": "Inserindo título do laudo…",
    "preamble": "Escrevendo preâmbulo…",
    "objective_heading": "Adicionando seção de objetivo…",
    "objective_body": "Registrando objetivo do exame…",
    "requisition_heading": "Abrindo dados da requisição…",
    "requisition_list": "Listando dados da requisição…",
    "attendance_heading": "Abrindo dados do atendimento…",
    "attendance_list": "Listando dados do atendimento…",
    "body_spacer": "Organizando fechamento…",
    "closing_phrase": "Inserindo encerramento…",
    "closing_notice": "Registrando arquivamento digital…",
    "signature": "Posicionando assinatura…",
    "finalize": "Finalizando laudo…",
}


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
    for step_id in BUILD_STEP_IDS:
        _run_build_step(step_id, ctx)

    return ctx.node_registry


def _complete_bootstrap_after_build(
    report: Report,
    metadata: CaseMetadata,
    *,
    nodes: dict[str, str] | None = None,
) -> str:
    """Finaliza metadados do bootstrap após montagem completa do corpo."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    resolved_nodes = dict(nodes or bootstrap.get("nodes") or {})

    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    bootstrap["metadata"] = case_metadata_to_form_dict(metadata)
    bootstrap["nodes"] = resolved_nodes
    bootstrap["pending_prompts"] = compute_pending_prompts(metadata, skipped=skipped)
    bootstrap["skipped_prompts"] = sorted(skipped)
    final_state = resolve_bootstrap_state(metadata, skipped=skipped)
    bootstrap["state"] = final_state
    bootstrap["workflow"] = GENERIC_WORKFLOW.slug
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    return final_state


@transaction.atomic
def advance_forensic_body_build_step(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
) -> tuple[list[ReportNode], bool, str, str | None]:
    """
    Avança um passo na montagem incremental do laudo.

    Retorna nós criados, conclusão, estado final do bootstrap e rótulo do passo.
    """
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    metadata = metadata_from_bootstrap(report.page_layout)
    progress = _get_build_progress(report.page_layout)
    step_index = int(progress.get("step_index", 0)) if progress else 0

    if progress is None:
        clear_report_body_nodes(report)
        set_bootstrap_state(report, STATE_BUILDING)
        progress = {"step_index": 0, "position": 1, "nodes": {}}

    if step_index >= len(BUILD_STEP_IDS):
        final_state = _complete_bootstrap_after_build(report, metadata)
        _save_build_progress(report, None)
        report.save(update_fields=["page_layout", "updated_at"])
        return [], True, final_state, None

    step_id = BUILD_STEP_IDS[step_index]
    ctx = _context_from_progress(
        report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        progress=progress,
    )
    created_nodes = _run_build_step(step_id, ctx)

    progress["step_index"] = step_index + 1
    progress["position"] = ctx.position
    progress["nodes"] = ctx.node_registry
    _save_build_progress(report, progress)

    done = progress["step_index"] >= len(BUILD_STEP_IDS)
    final_state = STATE_BUILDING
    if done:
        final_state = _complete_bootstrap_after_build(report, metadata, nodes=ctx.node_registry)
        _save_build_progress(report, None)

    report.save(update_fields=["page_layout", "updated_at"])
    return created_nodes, done, final_state, step_id
