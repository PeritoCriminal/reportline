# reportline/reports/models/report_image.py
"""
Model de imagem enviada para blocos de relatório.

Persiste arquivo redimensionado em MEDIA e metadados de exibição
para referência no JSON do bloco.
"""

from django.db import models

from common.models import BaseModel

from .report import Report


def report_image_upload_path(instance, filename: str) -> str:
    """Monta caminho de upload por relatório e identificador da imagem."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"reports/{instance.report_id}/{instance.pk}.{extension}"


class ReportImage(BaseModel):
    """Arquivo de imagem associado a um relatório."""

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Relatório",
    )
    image = models.ImageField(
        upload_to=report_image_upload_path,
        verbose_name="Imagem",
    )
    width = models.PositiveIntegerField(verbose_name="Largura (px)")
    height = models.PositiveIntegerField(verbose_name="Altura (px)")
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome original do arquivo",
    )

    class Meta:
        verbose_name = "Imagem de relatório"
        verbose_name_plural = "Imagens de relatório"
        ordering = ["created_at"]

    def __str__(self):
        return f"Imagem {self.pk} — {self.report.title}"
