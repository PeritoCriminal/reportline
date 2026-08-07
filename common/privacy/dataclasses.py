# reportline/common/privacy/dataclasses.py
"""
Estruturas de dados do pipeline de sanitização de PII.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SanitizationResult:
    """Resultado da sanitização de um trecho antes de envio a API externa."""

    sanitized_text: str
    replacement_counts: dict[str, int] = field(default_factory=dict)
    blocked: bool = False
    block_reason: str = ""
    content_hash: str = ""
