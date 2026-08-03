"""
Armazenamento transitório de documentos enviados no intake.

Arquivos ficam em disco sob ``MEDIA_ROOT`` e são removidos após
a geração do laudo ou ao expirar a sessão de upload.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

TEMP_ROOT = Path("institution_ic_sp/forensic_report/temp")


def store_temp_uploads(session_key: str, files: list[UploadedFile]) -> list[str]:
    """
    Persiste arquivos enviados em diretório temporário da sessão.

    Retorna caminhos relativos a ``MEDIA_ROOT`` dos arquivos gravados.
    """
    if not files:
        return []

    target_dir = Path(settings.MEDIA_ROOT) / TEMP_ROOT / session_key
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_paths: list[str] = []

    for uploaded in files:
        original_name = Path(getattr(uploaded, "name", "documento")).name
        safe_name = f"{uuid.uuid4().hex}_{original_name}"
        destination = target_dir / safe_name
        with destination.open("wb") as output:
            for chunk in uploaded.chunks():
                output.write(chunk)
        stored_paths.append(str(TEMP_ROOT / session_key / safe_name))

    return stored_paths


def clear_temp_uploads(session_key: str) -> None:
    """Remove diretório temporário da sessão, se existir."""
    target_dir = Path(settings.MEDIA_ROOT) / TEMP_ROOT / session_key
    if not target_dir.exists():
        return

    for path in target_dir.iterdir():
        if path.is_file():
            path.unlink()
    target_dir.rmdir()
