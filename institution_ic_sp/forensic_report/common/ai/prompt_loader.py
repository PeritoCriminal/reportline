"""
Carregamento e composição de prompts de IA por workflow e tarefa.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_FORENSIC_REPORT_ROOT = Path(__file__).resolve().parents[2]
_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@lru_cache(maxsize=32)
def load_prompt_markdown(*, workflow_slug: str, task: str, name: str) -> str:
    """Lê arquivo Markdown de prompt do workflow informado."""
    path = (
        _FORENSIC_REPORT_ROOT
        / "workflows"
        / workflow_slug
        / "ai"
        / "prompts"
        / task
        / f"{name}.md"
    )
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def load_style_markdown(*, workflow_slug: str, name: str) -> str:
    """
    Lê arquivo Markdown de biblioteca de estilo do workflow informado.

    TODO(futuro): permitir fontes dinâmicas — laudos anteriores do próprio
    perito ou trechos curados de laudos públicos de outros peritos — em
    substituição ou complemento aos exemplos fictícios estáticos.
    """
    path = (
        _FORENSIC_REPORT_ROOT
        / "workflows"
        / workflow_slug
        / "ai"
        / "style"
        / f"{name}.md"
    )
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=8)
def load_case_metadata_schema_summary() -> str:
    """Resume campos esperados no JSON de metadados para instrução da IA."""
    schema_path = Path(__file__).resolve().parent / "schemas" / "case_metadata.v1.json"
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    lines = [
        "Responda exclusivamente com JSON contendo as chaves abaixo.",
        "Use string vazia ou null quando o dado não constar nos documentos.",
        "",
    ]
    for field_name, spec in payload["properties"].items():
        description = spec.get("description", "")
        field_type = spec.get("type", "string")
        lines.append(f"- {field_name} ({field_type}): {description}")
    return "\n".join(lines)


def render_prompt_template(template: str, **context: str) -> str:
    """Substitui placeholders ``{{nome}}`` por valores do contexto."""
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return context.get(key, "")

    return _PLACEHOLDER_PATTERN.sub(replace, template)
