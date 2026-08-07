# reportline/scripts/add_path_headers.py
"""Adiciona comentário de path na primeira linha dos arquivos de texto do repositório."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "reportline"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
}
SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pdf",
    ".sqlite3",
    ".db",
    ".zip",
    ".tar",
    ".gz",
    ".whl",
    ".egg",
    ".lock",
    ".json",
    ".mo",
    ".webmanifest",
}


def comment_for(rel_path: str, ext: str, name: str) -> str | None:
    """Retorna a linha de comentário de path conforme a extensão do arquivo."""
    path = f"{PREFIX}/{rel_path}"
    if ext == ".html":
        return f"{{# {path} #}}"
    if ext == ".css":
        return f"/* {path} */"
    if ext in {".js", ".mjs", ".cjs"}:
        return f"// {path}"
    if ext == ".sql":
        return f"-- {path}"
    if ext in {
        ".py",
        ".md",
        ".mdc",
        ".txt",
        ".ini",
        ".cfg",
        ".yml",
        ".yaml",
        ".toml",
        ".sh",
        ".ps1",
        ".bat",
        ".gitignore",
        ".gitattributes",
        ".po",
    } or name.endswith(".example") or name in {
        "Dockerfile",
        "Makefile",
        "requirements.txt",
        "requirements-server.txt",
        "requirements-dev.txt",
        ".env.example",
        "env.example",
        ".gitkeep",
        ".gitignore",
        ".gitattributes",
    } or name.startswith(".env"):
        return f"# {path}"
    if ext == "" and name in {"Dockerfile", "Makefile", ".gitignore", ".gitkeep"}:
        return f"# {path}"
    return None


def has_path_comment(line: str) -> bool:
    """Verifica se a linha já contém o comentário de path padronizado."""
    stripped = line.strip()
    return (
        stripped.startswith(f"# {PREFIX}/")
        or stripped.startswith(f"{{# {PREFIX}/")
        or stripped.startswith(f"// {PREFIX}/")
        or stripped.startswith(f"/* {PREFIX}/")
        or stripped.startswith(f"-- {PREFIX}/")
    )


def insert_comment(content: str, comment: str) -> str:
    """Insere o comentário de path, preservando shebang quando presente."""
    if not content:
        return comment + "\n"

    lines = content.splitlines(keepends=True)
    if not lines:
        return comment + "\n"

    insert_at = 1 if lines[0].startswith("#!") else 0
    if insert_at < len(lines) and has_path_comment(lines[insert_at]):
        return content
    if has_path_comment(lines[0]):
        return content

    new_line = comment + "\n"
    if insert_at == 0:
        return new_line + content
    return lines[0] + new_line + "".join(lines[1:])


def main() -> None:
    """Percorre o repositório e adiciona headers de path onde faltarem."""
    updated: list[str] = []
    skipped: list[str] = []
    unknown: list[str] = []

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            file_path = Path(dirpath) / name
            ext = file_path.suffix.lower()
            if ext in SKIP_EXTENSIONS:
                skipped.append(str(file_path.relative_to(ROOT)))
                continue

            rel = file_path.relative_to(ROOT).as_posix()
            comment = comment_for(rel, ext, name)
            if comment is None:
                unknown.append(rel)
                continue

            try:
                raw = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                skipped.append(rel)
                continue

            new_raw = insert_comment(raw, comment)
            if new_raw != raw:
                file_path.write_text(new_raw, encoding="utf-8", newline="")
                updated.append(rel)

    print(f"Updated: {len(updated)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Unknown ext: {len(unknown)}")
    if unknown:
        for item in sorted(set(unknown))[:50]:
            print(f" ? {item}")


if __name__ == "__main__":
    main()
