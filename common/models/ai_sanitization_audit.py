"""
Auditoria de sanitização pré-envio a provedores externos de IA.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models.base_model import BaseModel


class AiSanitizationAudit(BaseModel):
    """
    Registro de sanitização antes de chamadas a IA externa.

    Não armazena texto bruto nem prompts — apenas hash, contadores e metadados.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_sanitization_audits",
        verbose_name="Usuário",
    )
    report = models.ForeignKey(
        "reports.Report",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_sanitization_audits",
        verbose_name="Laudo",
    )
    operation = models.CharField(
        max_length=64,
        verbose_name="Operação",
        help_text="Identificador da operação de IA (ex.: metadata_extraction).",
    )
    content_hash = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Hash do conteúdo",
        help_text="SHA-256 do texto original antes da sanitização.",
    )
    replacement_counts = models.JSONField(
        default=dict,
        verbose_name="Substituições",
        help_text="Contagem de substituições por tipo/categoria.",
    )
    blocked = models.BooleanField(
        default=False,
        verbose_name="Bloqueado",
    )
    block_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Motivo do bloqueio",
    )
    provider = models.CharField(
        max_length=32,
        default="openai",
        verbose_name="Provedor",
    )
    model_name = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Modelo",
    )

    class Meta:
        verbose_name = "Auditoria de sanitização para IA"
        verbose_name_plural = "Auditorias de sanitização para IA"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.operation} ({self.created_at:%Y-%m-%d %H:%M})"
