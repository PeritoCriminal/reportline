# reportline/institution_ic_sp/forensic_report/common/ai/sanitization/forensic_patterns.py
"""
Padrões regex de documentos periciais e policiais (IC-SP).
"""

from __future__ import annotations

import re

FORENSIC_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\bBO[-\s./]*\d[\d./-]*", re.IGNORECASE),
        "[NUMERO_REMOVIDO]",
        "BO",
    ),
    (
        re.compile(r"\bIP[-\s./]*\d[\d./-]*", re.IGNORECASE),
        "[NUMERO_REMOVIDO]",
        "IP",
    ),
    (
        re.compile(r"\bRDO[-\s./]*\d[\d./-]*", re.IGNORECASE),
        "[NUMERO_REMOVIDO]",
        "RDO",
    ),
    (
        re.compile(
            r"\bLaudo\s*(?:n[ºo°.]?\s*)?\d[\d./-]*",
            re.IGNORECASE,
        ),
        "[NUMERO_REMOVIDO]",
        "LAUDO",
    ),
    (
        re.compile(r"\bInqu[eé]rito\s*(?:n[ºo°.]?\s*)?\d[\d./-]*", re.IGNORECASE),
        "[NUMERO_REMOVIDO]",
        "INQUERITO",
    ),
    (
        re.compile(r"\b[A-Z]{3}\d[A-Z]\d{2}\b"),
        "[PLACA_REMOVIDA]",
        "PLACA",
    ),
    (
        re.compile(r"\b[A-Z]{3}-?\d{4}\b"),
        "[PLACA_REMOVIDA]",
        "PLACA",
    ),
    (
        re.compile(r"\bProtocolo[-\s.:]*\d[\d./-]*", re.IGNORECASE),
        "[NUMERO_REMOVIDO]",
        "PROTOCOLO",
    ),
)

RESIDUAL_FORENSIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    rule[0] for rule in FORENSIC_RULES
)


def apply_forensic_regex_rules(text: str) -> tuple[str, dict[str, int]]:
    """Aplica substituições regex forenses e retorna contadores por tipo."""
    counts: dict[str, int] = {}
    current = text
    for pattern, replacement, label in FORENSIC_RULES:
        current, replaced = pattern.subn(replacement, current)
        if replaced:
            counts[label] = counts.get(label, 0) + replaced
    return current, counts


def residual_pii_patterns() -> tuple[re.Pattern[str], ...]:
    """Retorna padrões usados na validação residual pós-sanitização."""
    from common.privacy.services.regex_patterns import RESIDUAL_GENERIC_PATTERNS

    return RESIDUAL_GENERIC_PATTERNS + RESIDUAL_FORENSIC_PATTERNS
