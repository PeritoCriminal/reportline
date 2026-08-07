# reportline/common/privacy/services/audit.py
"""
Persistência de auditoria do pipeline de sanitização para IA externa.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from django.conf import settings

from common.models.ai_sanitization_audit import AiSanitizationAudit
from common.privacy.dataclasses import SanitizationResult

logger = logging.getLogger(__name__)


def record_ai_sanitization_audit(
    *,
    context: dict[str, Any] | None,
    results: list[SanitizationResult],
) -> None:
    """
    Grava auditoria agregada das partes sanitizadas de uma chamada de IA.

    Usa o hash e contadores do primeiro resultado não vazio; marca bloqueio
    se qualquer parte tiver sido bloqueada.
    """
    if not results:
        return

    ctx = context or {}
    operation = str(ctx.get("operation", "unknown")).strip() or "unknown"
    user_id = _parse_uuid(ctx.get("user_id"))
    report_id = _parse_uuid(ctx.get("report_id"))

    primary = next((item for item in results if item.content_hash), results[0])
    blocked_result = next((item for item in results if item.blocked), None)

    aggregated_counts: dict[str, int] = {}
    for result in results:
        for key, value in result.replacement_counts.items():
            aggregated_counts[key] = aggregated_counts.get(key, 0) + int(value)

    try:
        AiSanitizationAudit.objects.create(
            user_id=user_id,
            report_id=report_id,
            operation=operation,
            content_hash=primary.content_hash,
            replacement_counts=aggregated_counts,
            blocked=any(item.blocked for item in results),
            block_reason=(blocked_result.block_reason if blocked_result else ""),
            provider=str(ctx.get("provider", "openai")),
            model_name=str(
                ctx.get("model_name")
                or getattr(settings, "FORENSIC_AI_MODEL", "")
            ),
        )
    except Exception:
        logger.exception("Falha ao registrar auditoria de sanitização para IA.")


def _parse_uuid(value: Any) -> UUID | None:
    """Converte identificador opcional em UUID."""
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
