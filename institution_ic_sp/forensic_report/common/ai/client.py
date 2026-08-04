"""
Cliente fino para chamadas JSON à API OpenAI no fluxo de laudo pericial.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


def is_ai_configured() -> bool:
    """Indica se a chave OpenAI está disponível para inferência."""
    return bool(getattr(settings, "OPENAI_API_KEY", ""))


def complete_json_chat(*, system: str, user: str) -> dict[str, Any] | None:
    """
    Solicita resposta estruturada em JSON ao modelo configurado.

    Retorna ``None`` quando a IA não estiver configurada ou a chamada falhar.
    """
    if not is_ai_configured():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.exception("Pacote openai não instalado.")
        return None

    model = getattr(settings, "FORENSIC_AI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception:
        logger.exception("Falha na chamada OpenAI para extração de metadados.")
        return None

    content = response.choices[0].message.content
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Resposta OpenAI não é JSON válido.")
        return None

    if not isinstance(parsed, dict):
        logger.warning("Resposta OpenAI não é objeto JSON.")
        return None

    return parsed
