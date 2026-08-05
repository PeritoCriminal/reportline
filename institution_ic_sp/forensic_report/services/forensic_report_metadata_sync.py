"""
Sincronização de metadados administrativos com blocos do laudo pericial.

Atualiza nós já mapeados no bootstrap quando o perito responde prompts
inline ou revisa dados administrativos.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import (
    CaseMetadata,
    UPPERCASE_TEXT_FIELDS,
    normalize_case_metadata,
    normalize_text_field,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    _parse_date,
    _parse_datetime,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    get_bootstrap_meta,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap_field_coverage import (
    ALL_PROMPT_FIELD_NAMES,
    DATE_PROMPT_FIELD_NAMES,
    DATETIME_PROMPT_FIELD_NAMES,
    TEXT_PROMPT_FIELD_NAMES,
)
from institution_ic_sp.forensic_report.services.forensic_report_body_builder import (
    update_header_report_number,
)
from institution_ic_sp.forensic_report.services.preamble import build_preamble_paragraph
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportBlock, ReportBlockType, ReportNode
from reports.models.report_block import ReportBlockLineSpacing
from reports.services.report_block_content import normalize_block_content
from reports.services.report_block_indent import MAX_INDENT_LEVEL
from reports.services.report_tree import delete_node, update_node_block


def _wrap_preamble_text(text: str) -> str:
    """Envolve o preâmbulo em fonte 10 pt serifada para renderização no laudo."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    return (
        f'<span class="report-inline-font-xs report-inline-font-serif">{cleaned}</span>'
    )


def replace_metadata(metadata: CaseMetadata, **changes) -> CaseMetadata:
    """Retorna cópia de metadados com campos substituídos."""
    payload = metadata.__dict__.copy()
    payload.update(changes)
    return CaseMetadata(**payload)


def apply_prompt_field_value(metadata: CaseMetadata, field_name: str, raw_value: str) -> CaseMetadata:
    """Aplica valor informado pelo perito a um campo de metadados."""
    if field_name not in ALL_PROMPT_FIELD_NAMES:
        raise ValidationError("Campo de prompt não suportado.")

    cleaned = (raw_value or "").strip()
    if field_name in DATE_PROMPT_FIELD_NAMES:
        return normalize_case_metadata(
            replace_metadata(metadata, designation_date=_parse_date(cleaned))
        )
    if field_name in DATETIME_PROMPT_FIELD_NAMES:
        return normalize_case_metadata(
            replace_metadata(metadata, **{field_name: _parse_datetime(cleaned)})
        )
    normalized = (
        normalize_text_field(field_name, cleaned)
        if field_name in UPPERCASE_TEXT_FIELDS
        else cleaned
    )
    return normalize_case_metadata(replace_metadata(metadata, **{field_name: normalized}))


def validate_prompt_submit_value(field_name: str, raw_value: str) -> None:
    """Valida valor obrigatório ao confirmar prompt inline."""
    if not (raw_value or "").strip():
        raise ValidationError("Informe um valor ou use Pular.")


def _node_map(report: Report) -> dict[str, str]:
    """Retorna mapa semântico de nós persistido no bootstrap."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    nodes = bootstrap.get("nodes", {})
    return dict(nodes) if isinstance(nodes, dict) else {}


def _set_node_map_entry(report: Report, node_key: str, node_id: str) -> None:
    """Atualiza identificador semântico no bootstrap."""
    bootstrap = get_bootstrap_meta(report.page_layout) or {}
    nodes = dict(bootstrap.get("nodes", {}))
    nodes[node_key] = node_id
    bootstrap["nodes"] = nodes
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)


def _get_node(report: Report, node_key: str) -> ReportNode | None:
    """Carrega nó pelo identificador semântico do bootstrap."""
    node_id = _node_map(report).get(node_key)
    if not node_id:
        return None
    return ReportNode.objects.filter(pk=node_id, report=report).select_related("block").first()


@transaction.atomic
def sync_forensic_metadata_fields(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
    changed_fields: set[str],
) -> Report:
    """Atualiza blocos afetados pelos campos informados ou revisados."""
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    if {"report_number", "report_year"} & changed_fields:
        main_title = _get_node(report, "main_title")
        if main_title is not None:
            update_node_block(main_title, content={"text": metadata.main_title_text})
        report.title = metadata.list_title
        report.page_layout = update_header_report_number(report.page_layout, metadata)

    if "designation_date" in changed_fields:
        preamble = _get_node(report, "preamble")
        if preamble is not None:
            update_node_block(
                preamble,
                content={
                    "text": _wrap_preamble_text(
                        build_preamble_paragraph(
                            metadata,
                            examiner=examiner,
                            institution=institution,
                        )
                    )
                },
                indent_level=MAX_INDENT_LEVEL,
                first_line_indent=False,
                line_spacing=ReportBlockLineSpacing.COMPACT,
            )

    if "exam_objective" in changed_fields:
        objective_body = _get_node(report, "objective_body")
        if objective_body is not None:
            update_node_block(objective_body, content={"text": metadata.exam_objective.strip()})

    requisition_fields = {
        "requesting_authority",
        "police_district",
        "occurrence_report",
        "police_inquiry",
        "occurrence_at",
        "requisition_at",
    }
    if requisition_fields & changed_fields:
        _sync_list_section(
            report,
            heading_key="requisition_heading",
            list_key="requisition_list",
            items=metadata.requisition_list_items(),
        )

    attendance_fields = {
        "attendance_protocol",
        "examination_at",
        "photography",
        "scanning_3d",
        "sketch",
    }
    if attendance_fields & changed_fields:
        _sync_list_section(
            report,
            heading_key="attendance_heading",
            list_key="attendance_list",
            items=metadata.attendance_list_items(),
        )

    report.save(update_fields=["title", "page_layout", "updated_at"])
    return report


def _sync_list_section(
    report: Report,
    *,
    heading_key: str,
    list_key: str,
    items: list[str],
) -> None:
    """Atualiza ou cria lista administrativa vinculada a um título de seção."""
    list_node = _get_node(report, list_key)
    if list_node is not None:
        if items:
            update_node_block(list_node, content={"items": items})
        else:
            delete_node(list_node)
            bootstrap = get_bootstrap_meta(report.page_layout) or {}
            nodes = dict(bootstrap.get("nodes", {}))
            nodes.pop(list_key, None)
            bootstrap["nodes"] = nodes
            report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
        return

    if not items:
        return

    heading = _get_node(report, heading_key)
    if heading is None:
        return

    block = ReportBlock.objects.create(
        block_type=ReportBlockType.UNORDERED_LIST,
        content=normalize_block_content(ReportBlockType.UNORDERED_LIST, {"items": items}),
        title_level=0,
    )
    list_node = ReportNode.objects.create(
        report=report,
        block=block,
        position=heading.position + Decimal("0.1"),
    )
    _set_node_map_entry(report, list_key, str(list_node.pk))
