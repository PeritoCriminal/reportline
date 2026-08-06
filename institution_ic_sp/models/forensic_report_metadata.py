"""
Dossiê persistido de metadados confirmados em laudos periciais do IC-SP.

Armazena dados coletados e validados pelo perito em cada fase do workflow,
independentemente do JSON transitório de bootstrap no layout do laudo.
"""

from django.db import models

from common.models import BaseModel
from reports.models import Report


class ForensicReportMetadata(BaseModel):
    """
    Registro 1:1 com ``Report`` contendo o dossiê pericial confirmado.

    O campo ``data`` organiza fases (`initial_data`, `property_crime`, etc.)
    com entradas do perito, valores confirmados e metadados de inferência.
    """

    report = models.OneToOneField(
        Report,
        on_delete=models.CASCADE,
        related_name="forensic_metadata",
        verbose_name="Laudo",
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Dossiê",
        help_text="Metadados confirmados por fase do workflow pericial.",
    )

    class Meta:
        verbose_name = "Metadados do laudo pericial"
        verbose_name_plural = "Metadados de laudos periciais"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Dossiê — {self.report.title}"
