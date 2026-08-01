"""
Views JSON para persistência interativa de nós no editor.

Expõe criação de irmãos e atualização de blocos via PATCH/POST
para o JavaScript do editor de relatórios.
"""

from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from reports.models import Report, ReportBlockType, ReportNode
from reports.services.report_block_sequence import (
    get_next_sibling_block_type,
    is_list_block_type,
)
from reports.services.report_editor_context import render_editable_block_html
from reports.services.report_tree import (
    append_list_item,
    delete_node,
    insert_sibling_after,
    insert_sibling_before,
    reorder_heading_siblings,
    update_list_items,
    update_node_block,
)


class ReportAuthorMixin(LoginRequiredMixin):
    """Restringe operações ao autor do relatório da URL."""

    def get_report(self) -> Report:
        """Carrega relatório pertencente ao usuário autenticado."""
        return get_object_or_404(
            Report.objects.filter(author=self.request.user),
            pk=self.kwargs["pk"],
        )

    def get_node(self, report: Report) -> ReportNode:
        """Carrega nó do relatório com bloco associado."""
        return get_object_or_404(
            ReportNode.objects.select_related("block"),
            pk=self.kwargs["node_id"],
            report=report,
        )


def _parse_json_body(request) -> dict:
    """Interpreta corpo JSON da requisição ou levanta erro de validação."""
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Corpo JSON inválido.") from exc


def _validation_error_response(exc: ValidationError) -> JsonResponse:
    """Formata erros de validação para resposta JSON 400."""
    messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
    return JsonResponse({"errors": messages}, status=400)


class ReportNodeDetailView(ReportAuthorMixin, View):
    """Atualiza ou exclui um nó existente (PATCH/DELETE)."""

    def patch(self, request, pk, node_id):
        """Persiste conteúdo do bloco ou acrescenta item de lista."""
        report = self.get_report()
        node = self.get_node(report)

        try:
            payload = _parse_json_body(request)
        except ValidationError as exc:
            return _validation_error_response(exc)

        try:
            if payload.get("append_list_item"):
                if not is_list_block_type(node.block.block_type):
                    raise ValidationError("Apenas listas aceitam novo item.")
                items = payload.get("items", [])
                if not isinstance(items, list):
                    raise ValidationError("Itens da lista devem ser uma lista.")
                node, new_index = append_list_item(
                    node,
                    items=[str(item) for item in items],
                )
                return JsonResponse(
                    {
                        "node_id": str(node.pk),
                        "block_type": node.block.block_type,
                        "title_level": node.block.title_level,
                        "content": node.block.content,
                        "new_item_index": new_index,
                    }
                )

            if payload.get("update_list_items"):
                if not is_list_block_type(node.block.block_type):
                    raise ValidationError("Apenas listas aceitam atualização de itens.")
                items = payload.get("items", [])
                if not isinstance(items, list):
                    raise ValidationError("Itens da lista devem ser uma lista.")
                node = update_list_items(node, items=[str(item) for item in items])
                block = node.block
                return JsonResponse(
                    {
                        "node_id": str(node.pk),
                        "block_type": block.block_type,
                        "title_level": block.title_level,
                        "content": block.content,
                    }
                )

            content = payload.get("content")
            block_type = payload.get("block_type")
            title_level = payload.get("title_level")
            text_align = payload.get("text_align")
            indent_level = payload.get("indent_level")
            first_line_indent = payload.get("first_line_indent")
            refresh_html = bool(payload.get("refresh_html"))
            focus_table_part = payload.get("focus_table_part")
            focus_table_row = payload.get("focus_table_row")
            focus_table_col = payload.get("focus_table_col")
            structure_changed = block_type is not None or title_level is not None

            layout_patch = (
                text_align is not None
                or indent_level is not None
                or first_line_indent is not None
            )
            if content is None and not layout_patch:
                raise ValidationError(
                    "Informe content, text_align, indent_level ou first_line_indent."
                )

            node = update_node_block(
                node,
                content=content,
                block_type=block_type,
                title_level=title_level,
                text_align=text_align,
                indent_level=indent_level,
                first_line_indent=first_line_indent,
            )
        except ValidationError as exc:
            return _validation_error_response(exc)

        block = node.block
        response = {
            "node_id": str(node.pk),
            "block_type": block.block_type,
            "title_level": block.title_level,
            "content": block.content,
            "text_align": block.text_align,
            "indent_level": block.indent_level,
            "first_line_indent": block.first_line_indent,
        }
        if structure_changed or refresh_html:
            focus_kwargs = {}
            if focus_table_part in ("header", "cell"):
                focus_kwargs["focus_table_part"] = focus_table_part
            if focus_table_row is not None:
                focus_kwargs["focus_table_row"] = int(focus_table_row)
            if focus_table_col is not None:
                focus_kwargs["focus_table_col"] = int(focus_table_col)
            response["html"] = render_editable_block_html(
                node,
                request,
                autofocus=True,
                **focus_kwargs,
            )
        return JsonResponse(response)

    def delete(self, request, pk, node_id):
        """Remove nó vazio do relatório."""
        report = self.get_report()
        node = self.get_node(report)

        try:
            delete_node(node)
        except ValidationError as exc:
            return _validation_error_response(exc)

        return JsonResponse({"deleted": True, "node_id": str(node_id)})

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        return HttpResponseNotAllowed(["PATCH", "DELETE"])


class ReportNodeCreateView(ReportAuthorMixin, View):
    """Insere nó irmão antes ou depois de um nó existente (POST)."""

    def post(self, request, pk):
        """Cria bloco irmão e retorna HTML renderizado para inserção no DOM."""
        report = self.get_report()

        try:
            payload = _parse_json_body(request)
        except ValidationError as exc:
            return _validation_error_response(exc)

        after_node_id = payload.get("after_node_id")
        before_node_id = payload.get("before_node_id")
        if bool(after_node_id) == bool(before_node_id):
            return JsonResponse(
                {"errors": ["Informe after_node_id ou before_node_id."]},
                status=400,
            )

        reference_node = get_object_or_404(
            ReportNode.objects.select_related("block"),
            pk=after_node_id or before_node_id,
            report=report,
        )

        try:
            block_type = payload.get("block_type")
            if not block_type:
                block_type = get_next_sibling_block_type(reference_node.block.block_type)

            is_caption = payload.get(
                "is_caption",
                after_node_id
                and reference_node.block.block_type == ReportBlockType.IMAGE,
            )
            caption_flag = bool(is_caption) and block_type == ReportBlockType.PARAGRAPH
            indent_level = payload.get("indent_level")
            first_line_indent = payload.get("first_line_indent")

            if before_node_id:
                node = insert_sibling_before(
                    report,
                    reference_node,
                    block_type=block_type,
                    content=payload.get("content"),
                    title_level=payload.get("title_level"),
                    is_caption=caption_flag,
                    indent_level=indent_level,
                    first_line_indent=first_line_indent,
                )
            else:
                node = insert_sibling_after(
                    report,
                    reference_node,
                    block_type=block_type,
                    content=payload.get("content"),
                    title_level=payload.get("title_level"),
                    is_caption=caption_flag,
                    indent_level=indent_level,
                    first_line_indent=first_line_indent,
                )
        except ValidationError as exc:
            return _validation_error_response(exc)

        html = render_editable_block_html(
            node,
            request,
            autofocus=True,
            is_caption=is_caption and block_type == ReportBlockType.PARAGRAPH,
        )
        block = node.block
        return JsonResponse(
            {
                "node_id": str(node.pk),
                "block_type": block.block_type,
                "title_level": block.title_level,
                "content": block.content,
                "html": html,
                "text_align": block.text_align,
                "indent_level": block.indent_level,
                "first_line_indent": block.first_line_indent,
                "is_caption": is_caption and block_type == ReportBlockType.PARAGRAPH,
                "insertion": "before" if before_node_id else "after",
            }
        )

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        return HttpResponseNotAllowed(["POST"])


class ReportNodeReorderView(ReportAuthorMixin, View):
    """Reordena títulos irmãos no sumário do editor (POST)."""

    def post(self, request, pk):
        """Persiste nova ordem de nós heading sob o mesmo pai."""
        from uuid import UUID

        report = self.get_report()

        try:
            payload = _parse_json_body(request)
        except ValidationError as exc:
            return _validation_error_response(exc)

        parent_raw = payload.get("parent_node_id")
        if parent_raw in (None, ""):
            parent_id = None
        else:
            try:
                parent_id = UUID(str(parent_raw))
            except (ValueError, TypeError):
                return _validation_error_response(
                    ValidationError("parent_node_id inválido.")
                )
            get_object_or_404(ReportNode, pk=parent_id, report=report)

        ordered_raw = payload.get("ordered_node_ids")
        if not isinstance(ordered_raw, list):
            return JsonResponse(
                {"errors": ["ordered_node_ids deve ser uma lista."]},
                status=400,
            )

        try:
            ordered_heading_ids = [UUID(str(item)) for item in ordered_raw]
        except (ValueError, TypeError):
            return _validation_error_response(
                ValidationError("ordered_node_ids contém identificadores inválidos.")
            )

        try:
            reorder_heading_siblings(report, parent_id, ordered_heading_ids)
        except ValidationError as exc:
            return _validation_error_response(exc)

        return JsonResponse({"ok": True})

    def http_method_not_allowed(self, request, *args, **kwargs):
        """Restringe métodos aceitos neste endpoint."""
        return HttpResponseNotAllowed(["POST"])
