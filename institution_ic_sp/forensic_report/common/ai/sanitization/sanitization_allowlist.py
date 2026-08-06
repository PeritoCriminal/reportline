"""
Termos institucionais preservados na sanitização pericial para IA externa.
"""

from __future__ import annotations

from django.conf import settings

from common.privacy.services.sanitization_allowlist import fold_text_for_allowlist

DEFAULT_FORENSIC_SANITIZATION_ALLOWLIST: tuple[str, ...] = (
    "autoridade requisitante",
    "fotografo",
    "fotografo tecnico",
    "fotógrafo",
    "fotógrafo técnico",
    "croqui",
    "desenho",
    "desenhista",
    "desenhista tecnico",
    "desenhista técnico",
    "perito criminal",
    "perito criminal diretor",
    "escaneamento 3d",
    "escaneamento 3D",
    "escaner 3d",
    "escaner 3D",
    "imagens panoramicas",
    "imagens panorâmicas",
    "requisicao de exame pericial",
    "requisição de exame pericial",
    "boletim de ocorrencia",
    "boletim de ocorrência",
    "objetivo da pericia",
    "objetivo da perícia",
)


def get_forensic_sanitization_allowlist() -> tuple[str, ...]:
    """
    Retorna lista completa de termos preservados (padrão + settings).

    ``FORENSIC_AI_SANITIZATION_ALLOWLIST`` aceita termos extras separados
    por vírgula no ``.env``.
    """
    extra_raw = getattr(settings, "FORENSIC_AI_SANITIZATION_ALLOWLIST", ()) or ()
    if isinstance(extra_raw, str):
        extra = tuple(
            item.strip()
            for item in extra_raw.split(",")
            if item and item.strip()
        )
    else:
        extra = tuple(str(item).strip() for item in extra_raw if str(item).strip())

    merged: list[str] = []
    seen: set[str] = set()
    for term in (*DEFAULT_FORENSIC_SANITIZATION_ALLOWLIST, *extra):
        folded = fold_text_for_allowlist(term)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        merged.append(term)
    return tuple(merged)
