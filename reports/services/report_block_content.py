"""
Normalização e conteúdo padrão de blocos de relatório.

Valida payloads JSON por ``block_type`` antes da persistência
nas operações interativas do editor.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from reports.models import ReportBlockType


def default_content_for_block_type(block_type: str) -> dict[str, Any]:
    """Retorna payload JSON inicial vazio conforme o tipo de bloco."""
    if block_type == ReportBlockType.HEADING:
        return {"text": ""}
    if block_type == ReportBlockType.PARAGRAPH:
        return {"text": ""}
    if block_type in (ReportBlockType.ORDERED_LIST, ReportBlockType.UNORDERED_LIST):
        return {"items": [""]}
    if block_type == ReportBlockType.LINK:
        return {"text": "", "url": ""}
    if block_type == ReportBlockType.TABLE:
        return {"headers": [], "rows": []}
    if block_type == ReportBlockType.IMAGE:
        return {"alt": "", "file": ""}
    raise ValidationError("Tipo de bloco não suportado.")


def normalize_block_content(block_type: str, content: Any) -> dict[str, Any]:
    """
    Normaliza e valida o payload ``content`` para o tipo informado.

    Levanta ``ValidationError`` quando a estrutura não corresponde ao tipo.
    """
    if not isinstance(content, dict):
        raise ValidationError("Conteúdo do bloco deve ser um objeto JSON.")

    if block_type in (ReportBlockType.HEADING, ReportBlockType.PARAGRAPH):
        text = content.get("text", "")
        if not isinstance(text, str):
            raise ValidationError("O campo text deve ser texto.")
        return {"text": text}

    if block_type in (ReportBlockType.ORDERED_LIST, ReportBlockType.UNORDERED_LIST):
        items = content.get("items", [])
        if not isinstance(items, list):
            raise ValidationError("O campo items deve ser uma lista.")
        return {"items": [str(item) for item in items]}

    if block_type == ReportBlockType.LINK:
        text = content.get("text", "")
        url = content.get("url", "")
        if not isinstance(text, str) or not isinstance(url, str):
            raise ValidationError("Link exige text e url como texto.")
        return {"text": text, "url": url}

    if block_type == ReportBlockType.TABLE:
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        if not isinstance(headers, list) or not isinstance(rows, list):
            raise ValidationError("Tabela exige headers e rows como listas.")
        return {
            "headers": [str(header) for header in headers],
            "rows": [[str(cell) for cell in row] for row in rows],
        }

    if block_type == ReportBlockType.IMAGE:
        alt = content.get("alt", "")
        file_ref = content.get("file", "")
        if not isinstance(alt, str) or not isinstance(file_ref, str):
            raise ValidationError("Imagem exige alt e file como texto.")
        return {"alt": alt, "file": file_ref}

    raise ValidationError("Tipo de bloco não suportado.")
