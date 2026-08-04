"""
Extração de texto de documentos enviados no intake, em memória.

Converte PDFs em texto e registra imagens sem OCR local para uso futuro
com modelos multimodais.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from pypdf import PdfReader

PDF_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
    }
)
IMAGE_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }
)
MAX_PAGES_PER_PDF = 30
MAX_CHARS_TOTAL = 120_000


def _guess_kind(uploaded: UploadedFile) -> str:
    """Classifica upload como pdf, image ou unknown."""
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    name = (getattr(uploaded, "name", "") or "").lower()
    suffix = Path(name).suffix

    if content_type in PDF_CONTENT_TYPES or suffix == ".pdf":
        return "pdf"
    if content_type in IMAGE_CONTENT_TYPES or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return "image"
    return "unknown"


def _extract_pdf_text(uploaded: UploadedFile) -> str:
    """Extrai texto de PDF até o limite de páginas configurado."""
    payload = uploaded.read()
    uploaded.seek(0)
    reader = PdfReader(BytesIO(payload))
    chunks: list[str] = []
    for index, page in enumerate(reader.pages):
        if index >= MAX_PAGES_PER_PDF:
            break
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(page_text.strip())
    return "\n\n".join(chunks)


def extract_text_from_uploads(uploaded_files: list[UploadedFile] | None) -> str:
    """
    Concatena trechos legíveis de todos os uploads.

    Imagens sem OCR local geram marcador descritivo para orientar a IA ou
    revisão manual do perito.
    """
    if not uploaded_files:
        return ""

    sections: list[str] = []
    total_chars = 0

    for uploaded in uploaded_files:
        original_name = Path(getattr(uploaded, "name", "documento")).name
        kind = _guess_kind(uploaded)
        section_body = ""

        if kind == "pdf":
            section_body = _extract_pdf_text(uploaded)
        elif kind == "image":
            section_body = (
                "[Imagem anexada sem OCR local. Extraia apenas metadados visíveis "
                "se o serviço suportar visão; caso contrário, ignore.]"
            )
        else:
            section_body = "[Formato não suportado para extração automática de texto.]"

        if not section_body.strip():
            section_body = "[Nenhum texto legível extraído deste arquivo.]"

        remaining = MAX_CHARS_TOTAL - total_chars
        if remaining <= 0:
            break
        if len(section_body) > remaining:
            section_body = section_body[:remaining] + "\n[... texto truncado ...]"

        sections.append(f"### Arquivo: {original_name}\n{section_body}")
        total_chars += len(section_body)

    return "\n\n".join(sections).strip()
