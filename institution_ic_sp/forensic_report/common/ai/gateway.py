# reportline/institution_ic_sp/forensic_report/common/ai/gateway.py
"""
Porta de saída única para IA externa.

A sanitização de PII aplica-se **somente** a texto extraído de documentos enviados
pelo usuário. Caixas de texto de prompts, orientações e legendas propostas são
preservadas integralmente.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from common.privacy.exceptions import ExternalAiBlockedError
from common.privacy.services.audit import record_ai_sanitization_audit
from institution_ic_sp.forensic_report.common.ai.client import (
    complete_json_chat,
    is_ai_configured,
)
from institution_ic_sp.forensic_report.common.ai.sanitization.forensic_sanitizer import (
    sanitize_forensic_text_for_external_ai,
)

logger = logging.getLogger(__name__)


def _sanitize_parts(
    *,
    parts: list[str],
    audit_context: dict[str, Any] | None,
) -> list[str]:
    """Sanitiza trechos documentais, audita e levanta erro se bloqueado."""
    results = [sanitize_forensic_text_for_external_ai(part) for part in parts]
    record_ai_sanitization_audit(context=audit_context, results=results)

    blocked = next((item for item in results if item.blocked), None)
    if blocked:
        raise ExternalAiBlockedError(blocked.block_reason)

    return [item.sanitized_text for item in results]


def sanitize_uploaded_document_text(
    text: str,
    *,
    audit_context: dict[str, Any] | None = None,
) -> str:
    """
    Sanitiza texto extraído de documentos anexados pelo usuário.

    Caixas de prompt e orientações do perito **não** devem passar por esta função.
    """
    cleaned = text.strip()
    if not cleaned:
        return text
    return _sanitize_parts(parts=[cleaned], audit_context=audit_context)[0]


def complete_json_chat_safe(
    *,
    system: str,
    user: str,
    audit_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Chama a OpenAI com prompts montados localmente.

    O conteúdo de ``system`` e ``user`` é enviado sem sanitização adicional — a
    higienização de PII deve ocorrer apenas nos trechos documentais antes da
    montagem do prompt (``sanitize_uploaded_document_text``).
    """
    del audit_context  # reservado para compatibilidade de assinatura
    if not is_ai_configured():
        return None

    return complete_json_chat(system=system, user=user)


def complete_json_with_images_safe(
    *,
    system: str,
    user_text: str,
    image_data_urls: list[str] | None = None,
    allow_external_images: bool = False,
    audit_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Chama OpenAI com imagens opcionais.

    O texto do prompt é preservado; somente trechos documentais devem ser
    sanitizados previamente. Imagens só são enviadas quando
    ``allow_external_images`` for verdadeiro (habilitação por perfil do perito).
    """
    if not is_ai_configured():
        return None

    urls = list(image_data_urls or [])
    if urls and not allow_external_images:
        logger.info(
            "Imagens omitidas da chamada externa: perito sem permissão (%s).",
            (audit_context or {}).get("operation", "unknown"),
        )
        urls = []

    try:
        from openai import OpenAI
    except ImportError:
        logger.exception("Pacote openai não instalado.")
        return None

    import json

    model = getattr(settings, "FORENSIC_AI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for data_url in urls:
        user_content.append({"type": "image_url", "image_url": {"url": data_url}})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception:
        logger.exception("Falha na inferência multimodal de IA externa.")
        return None

    content = response.choices[0].message.content
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Resposta da IA externa não é JSON válido.")
        return None
    return parsed if isinstance(parsed, dict) else None
