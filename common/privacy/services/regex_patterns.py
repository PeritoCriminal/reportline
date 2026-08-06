"""
Padrões regex genéricos de PII para sanitização local.
"""

from __future__ import annotations

import re

GENERIC_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
        "[CPF_REMOVIDO]",
        "CPF",
    ),
    (
        re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-\d{1}\b"),
        "[RG_REMOVIDO]",
        "RG",
    ),
    (
        re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
            re.IGNORECASE,
        ),
        "[EMAIL_REMOVIDO]",
        "EMAIL",
    ),
    (
        re.compile(r"\b(?:\+55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}\b"),
        "[TELEFONE_REMOVIDO]",
        "PHONE",
    ),
    (
        re.compile(r"\b\d{5}-?\d{3}\b"),
        "[CEP_REMOVIDO]",
        "CEP",
    ),
)

RESIDUAL_GENERIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    rule[0] for rule in GENERIC_RULES
)


def apply_generic_regex_rules(text: str) -> tuple[str, dict[str, int]]:
    """Aplica substituições regex genéricas e retorna contadores por tipo."""
    counts: dict[str, int] = {}
    current = text
    for pattern, replacement, label in GENERIC_RULES:
        current, replaced = pattern.subn(replacement, current)
        if replaced:
            counts[label] = counts.get(label, 0) + replaced
    return current, counts
