# reportline/institution_ic_sp/forensic_report/common/ai/sanitization/forensic_sanitizer.py
"""
Sanitização de texto pericial antes de envio a IA externa.
"""

from __future__ import annotations

from common.privacy.dataclasses import SanitizationResult
from common.privacy.services.text_sanitizer import sanitize_text_for_external_ai
from institution_ic_sp.forensic_report.common.ai.sanitization.forensic_patterns import (
    RESIDUAL_FORENSIC_PATTERNS,
    apply_forensic_regex_rules,
)
from institution_ic_sp.forensic_report.common.ai.sanitization.sanitization_allowlist import (
    get_forensic_sanitization_allowlist,
)


def sanitize_forensic_text_for_external_ai(text: str) -> SanitizationResult:
    """Sanitiza texto do domínio pericial (regex forenses + pipeline base)."""
    return sanitize_text_for_external_ai(
        text,
        extra_regex_rules=apply_forensic_regex_rules,
        residual_patterns=lambda: RESIDUAL_FORENSIC_PATTERNS,
        allowlist_terms=get_forensic_sanitization_allowlist(),
    )
