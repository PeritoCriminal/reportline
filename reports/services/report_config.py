"""
Atualização de configuração do laudo e preferências do usuário.
"""

from __future__ import annotations

from uuid import UUID

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from reports.models import Report, ReportBlockType
from reports.services.report_caption_numbering import build_caption_number_map
from reports.services.report_editor_context import _group_nodes_by_parent, _is_caption_paragraph
from reports.services.report_heading_numbering import build_heading_number_map
from reports.services.report_user_config import (
    get_or_create_user_config,
    serialize_report_config,
)


@transaction.atomic
def update_report_config(
    report: Report,
    user: AbstractBaseUser,
    *,
    number_headings: bool,
    number_captions: bool,
    first_line_indent: bool,
) -> dict:
    """
    Persiste configuração no laudo, nas preferências do usuário e aplica recuo.

    O recuo de primeira linha é propagado a todos os parágrafos de corpo
    do laudo aberto; legendas permanecem sem recuo.
    """
    report.number_headings = bool(number_headings)
    report.number_captions = bool(number_captions)
    report.first_line_indent = bool(first_line_indent)
    report.save(
        update_fields=[
            "number_headings",
            "number_captions",
            "first_line_indent",
            "updated_at",
        ]
    )

    user_config = get_or_create_user_config(user)
    user_config.number_headings = report.number_headings
    user_config.number_captions = report.number_captions
    user_config.first_line_indent = report.first_line_indent
    user_config.save(
        update_fields=[
            "number_headings",
            "number_captions",
            "first_line_indent",
            "updated_at",
        ]
    )

    updated_paragraph_ids = apply_first_line_indent_to_report(report)
    refresh_payload = build_config_refresh_payload(report)

    payload = serialize_report_config(report)
    payload["paragraph_node_ids"] = [str(node_id) for node_id in updated_paragraph_ids]
    payload.update(refresh_payload)
    return payload


def apply_first_line_indent_to_report(report: Report) -> list[UUID]:
    """Atualiza recuo de 1ª linha em parágrafos de corpo conforme config do laudo."""
    nodes = list(
        report.nodes.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent = _group_nodes_by_parent(nodes)
    updated_ids: list[UUID] = []

    for node in nodes:
        block = node.block
        if block.block_type != ReportBlockType.PARAGRAPH:
            continue
        if _is_caption_paragraph(node, nodes_by_parent):
            continue
        if block.first_line_indent == report.first_line_indent:
            continue
        block.first_line_indent = report.first_line_indent
        block.save(update_fields=["first_line_indent", "updated_at"])
        updated_ids.append(node.pk)

    return updated_ids


def build_caption_numbers_payload(report: Report) -> dict[str, int]:
    """Retorna mapa serializado de legendas numeradas para respostas da API."""
    return build_config_refresh_payload(report)["caption_numbers"]


def build_config_refresh_payload(report: Report) -> dict:
    """Monta mapas de numeração para atualização parcial do editor."""
    nodes = list(
        report.nodes.select_related("block").order_by("position", "created_at")
    )
    nodes_by_parent = _group_nodes_by_parent(nodes)

    if report.number_headings:
        heading_numbers = build_heading_number_map(nodes_by_parent)
    else:
        heading_numbers = {}

    caption_numbers = build_caption_number_map(
        nodes_by_parent,
        number_captions=report.number_captions,
    )

    return {
        "heading_numbers": {str(node_id): number for node_id, number in heading_numbers.items()},
        "caption_numbers": {str(node_id): number for node_id, number in caption_numbers.items()},
    }
