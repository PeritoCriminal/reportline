"""
Limpeza da pasta de mídia associada a um relatório.
"""

from __future__ import annotations

import os
import shutil
import stat
from uuid import UUID

from django.core.files.storage import FileSystemStorage, default_storage

REPORT_MEDIA_ROOT = "reports"


def report_media_folder_relative_path(report_id: UUID | str) -> str:
    """Retorna caminho relativo da pasta de mídia do laudo no storage."""
    return f"{REPORT_MEDIA_ROOT}/{report_id}"


def _handle_rmtree_error(func, path, exc_info) -> None:
    """Torna arquivos somente leitura removíveis no Windows antes de repetir."""
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
        return
    raise exc_info[1]


def delete_report_media_folder(report_id: UUID | str) -> None:
    """
    Remove a pasta do laudo em MEDIA com todo o conteúdo.

    Operação idempotente: ausência da pasta não gera erro.
    """
    folder = report_media_folder_relative_path(report_id)

    if isinstance(default_storage, FileSystemStorage):
        absolute = default_storage.path(folder)
        if os.path.isdir(absolute):
            shutil.rmtree(absolute, onerror=_handle_rmtree_error)
        return

    if not _storage_folder_exists(folder):
        return

    _delete_storage_tree(folder)


def _storage_folder_exists(path: str) -> bool:
    """Verifica existência de prefixo/pasta no storage, inclusive quando vazio."""
    if default_storage.exists(path):
        return True
    try:
        default_storage.listdir(path)
    except (FileNotFoundError, NotImplementedError, OSError):
        return False
    return True


def _delete_storage_tree(path: str) -> None:
    """Remove recursivamente arquivos e subpastas via storage abstrato."""
    try:
        directories, files = default_storage.listdir(path)
    except (FileNotFoundError, OSError):
        return

    for name in files:
        default_storage.delete(f"{path}/{name}")
    for name in directories:
        _delete_storage_tree(f"{path}/{name}")

    if isinstance(default_storage, FileSystemStorage):
        absolute = default_storage.path(path)
        if os.path.isdir(absolute):
            os.rmdir(absolute)
