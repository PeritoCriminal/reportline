"""
Limpeza da pasta de mídia associada a um relatório.
"""

from __future__ import annotations

import os
import shutil
from uuid import UUID

from django.core.files.storage import FileSystemStorage, default_storage

REPORT_MEDIA_ROOT = "reports"


def report_media_folder_relative_path(report_id: UUID | str) -> str:
    """Retorna caminho relativo da pasta de mídia do laudo no storage."""
    return f"{REPORT_MEDIA_ROOT}/{report_id}"


def delete_report_media_folder(report_id: UUID | str) -> None:
    """
    Remove a pasta do laudo em MEDIA com todo o conteúdo.

    Operação idempotente: ausência da pasta não gera erro.
    """
    folder = report_media_folder_relative_path(report_id)
    if not default_storage.exists(folder):
        return

    if isinstance(default_storage, FileSystemStorage):
        shutil.rmtree(default_storage.path(folder))
        return

    _delete_storage_tree(folder)


def _delete_storage_tree(path: str) -> None:
    """Remove recursivamente arquivos e subpastas via storage abstrato."""
    directories, files = default_storage.listdir(path)
    for name in files:
        default_storage.delete(f"{path}/{name}")
    for name in directories:
        _delete_storage_tree(f"{path}/{name}")

    if isinstance(default_storage, FileSystemStorage):
        os.rmdir(default_storage.path(path))
