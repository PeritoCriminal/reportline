# reportline/reports/services/report_image_upload.py
"""
Persistência de imagens enviadas ao editor de relatório.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction

from reports.models import Report, ReportImage
from reports.services.report_image_processing import process_uploaded_image


@transaction.atomic
def store_report_image_from_bytes(
    report: Report,
    image_bytes: bytes,
    *,
    filename: str = "qrcode.png",
) -> ReportImage:
    """
    Persiste bytes PNG/JPEG como ``ReportImage`` vinculado ao laudo.

    Usado para QR codes gerados automaticamente durante a montagem do laudo.
    """
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO(image_bytes)
    with Image.open(buffer) as img:
        width, height = img.size

    report_image = ReportImage(
        report=report,
        width=width,
        height=height,
        original_filename=filename,
    )
    report_image.save()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    report_image.image.save(
        f"{report_image.pk}.{extension}",
        ContentFile(image_bytes),
        save=True,
    )
    return report_image


@transaction.atomic
def store_report_image(report: Report, uploaded_file) -> ReportImage:
    """
    Processa upload, redimensiona e grava ``ReportImage`` vinculado ao relatório.

    A imagem é salva com maior dimensão equivalente a 14 cm (96 DPI).
    """
    image_bytes, extension, width, height = process_uploaded_image(uploaded_file)
    original_name = getattr(uploaded_file, "name", "") or "imagem"

    report_image = ReportImage(
        report=report,
        width=width,
        height=height,
        original_filename=original_name,
    )
    report_image.save()
    report_image.image.save(
        f"{report_image.pk}.{extension}",
        ContentFile(image_bytes),
        save=True,
    )
    return report_image


def build_image_block_content(report_image: ReportImage) -> dict[str, str | int]:
    """Monta payload JSON do bloco de imagem a partir de ``ReportImage``."""
    return {
        "alt": "",
        "file": report_image.image.name,
        "image_id": str(report_image.pk),
        "width": report_image.width,
        "height": report_image.height,
    }


def delete_report_image(image_id) -> None:
    """Remove imagem persistida quando o bloco associado é excluído."""
    try:
        report_image = ReportImage.objects.get(pk=image_id)
    except ReportImage.DoesNotExist:
        return
    report_image.image.delete(save=False)
    report_image.delete()
