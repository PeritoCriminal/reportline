# reportline/common/privacy/services/text_sanitizer.py
"""
Pipeline base de sanitização de PII (regex genéricos + Presidio opcional).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from django.conf import settings

from common.privacy.dataclasses import SanitizationResult
from common.privacy.services.analyzer_registry import get_analyzer_engine
from common.privacy.services.regex_patterns import (
    RESIDUAL_GENERIC_PATTERNS,
    apply_generic_regex_rules,
)

PRESIDIO_ENTITIES = ("PERSON", "LOCATION")
PRESIDIO_PLACEHOLDERS = {
    "PERSON": "[NOME_REMOVIDO]",
    "LOCATION": "[LOCAL_REMOVIDO]",
}

ExtraRegexRules = Callable[[str], tuple[str, dict[str, int]]]
ResidualPatterns = Callable[[], tuple]


def sanitize_text_for_external_ai(
    text: str,
    *,
    extra_regex_rules: ExtraRegexRules | None = None,
    residual_patterns: ResidualPatterns | None = None,
    allowlist_terms: tuple[str, ...] | None = None,
) -> SanitizationResult:
    """
    Sanitiza texto antes de envio a provedor externo de IA.

    ``extra_regex_rules`` permite ao domínio aplicar padrões institucionais
    após os regex genéricos. ``residual_patterns`` complementa a checagem
    final de PII residual.
    """
    raw = (text or "").strip()
    if not raw:
        return SanitizationResult(sanitized_text="", content_hash=_hash_text(""))

    if not getattr(settings, "FORENSIC_AI_SANITIZATION_ENABLED", True):
        return SanitizationResult(sanitized_text=raw, content_hash=_hash_text(raw))

    counts: dict[str, int] = {}
    current = raw

    current, generic_counts = apply_generic_regex_rules(current)
    counts.update(generic_counts)

    if extra_regex_rules is not None:
        current, extra_counts = extra_regex_rules(current)
        counts.update(extra_counts)

    current, presidio_count = _apply_presidio(current, allowlist_terms=allowlist_terms)
    if presidio_count:
        counts["PRESIDIO"] = presidio_count

    blocked = False
    block_reason = ""
    patterns = list(RESIDUAL_GENERIC_PATTERNS)
    if residual_patterns is not None:
        patterns.extend(residual_patterns())

    if getattr(settings, "FORENSIC_AI_BLOCK_ON_RESIDUAL_PII", True) and _has_residual_pii(
        current, patterns
    ):
        blocked = True
        block_reason = (
            "Análise indisponível: o conteúdo contém dados sensíveis que "
            "não podem ser enviados a serviços externos."
        )

    return SanitizationResult(
        sanitized_text=current,
        replacement_counts=counts,
        blocked=blocked,
        block_reason=block_reason,
        content_hash=_hash_text(raw),
    )


def _apply_presidio(
    text: str,
    *,
    allowlist_terms: tuple[str, ...] | None = None,
) -> tuple[str, int]:
    """Anonimiza entidades PERSON/LOCATION via Presidio, quando disponível."""
    analyzer = get_analyzer_engine()
    if analyzer is None:
        return text, 0

    try:
        from presidio_anonymizer import AnonymizerEngine
        from presidio_anonymizer.entities import OperatorConfig
    except ImportError:
        return text, 0

    results = analyzer.analyze(text=text, language="pt", entities=list(PRESIDIO_ENTITIES))
    if not results:
        return text, 0

    if allowlist_terms:
        from common.privacy.services.sanitization_allowlist import filter_analyzer_results

        results = filter_analyzer_results(
            results,
            text=text,
            allowlist=allowlist_terms,
        )
        if not results:
            return text, 0

    operators = {
        "DEFAULT": OperatorConfig("replace", {"new_value": "[DADO_REMOVIDO]"}),
    }
    for entity, placeholder in PRESIDIO_PLACEHOLDERS.items():
        operators[entity] = OperatorConfig("replace", {"new_value": placeholder})

    anonymizer = AnonymizerEngine()
    output = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )
    return output.text, len(results)


def _has_residual_pii(text: str, patterns: list) -> bool:
    """Indica se ainda há padrões típicos de PII após sanitização."""
    return any(pattern.search(text) for pattern in patterns)


def _hash_text(value: str) -> str:
    """Calcula hash SHA-256 do texto original (nunca persistir o bruto)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
