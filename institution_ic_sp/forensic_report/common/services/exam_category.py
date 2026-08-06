"""
Categorias de exame pericial inferidas ou escolhidas no intake.
"""

from __future__ import annotations

import re
import unicodedata

EXAM_CATEGORY_PROPERTY_SCENE = "property_scene"
EXAM_CATEGORY_TRAFFIC_ACCIDENT = "traffic_accident"
EXAM_CATEGORY_WORK_ACCIDENT = "work_accident"
EXAM_CATEGORY_UNKNOWN = "unknown"

VALID_EXAM_CATEGORIES = frozenset(
    {
        EXAM_CATEGORY_PROPERTY_SCENE,
        EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        EXAM_CATEGORY_WORK_ACCIDENT,
        EXAM_CATEGORY_UNKNOWN,
    }
)

EXAM_CATEGORY_ALIASES: dict[str, str] = {
    "property_crime": EXAM_CATEGORY_PROPERTY_SCENE,
    "local_de_furto": EXAM_CATEGORY_PROPERTY_SCENE,
    "furto_a_residencia": EXAM_CATEGORY_PROPERTY_SCENE,
    "furto_residencia": EXAM_CATEGORY_PROPERTY_SCENE,
    "levantamento_de_local": EXAM_CATEGORY_PROPERTY_SCENE,
    "exame_de_local": EXAM_CATEGORY_PROPERTY_SCENE,
    "traffic": EXAM_CATEGORY_TRAFFIC_ACCIDENT,
    "acidente_de_transito": EXAM_CATEGORY_TRAFFIC_ACCIDENT,
    "work": EXAM_CATEGORY_WORK_ACCIDENT,
}

PROPERTY_SCENE_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"levantamento de local",
        r"exame pericial de local",
        r"exame de local",
        r"local de furto",
        r"local de roubo",
        r"local de dano",
        r"furto a residencia",
        r"furto qualificado",
        r"invasao a residencia",
        r"roubo a residencia",
        r"dano patrimonial",
        r"crime patrimonial",
    )
)

TRAFFIC_ACCIDENT_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"acidente de transito",
        r"sinistro de transito",
        r"colisao de transito",
    )
)

WORK_ACCIDENT_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"acidente de trabalho",
        r"acidente do trabalho",
    )
)

DEFERRED_MODULE_CATEGORIES = frozenset(
    {
        EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        EXAM_CATEGORY_WORK_ACCIDENT,
    }
)

EXAM_CATEGORY_LABELS: dict[str, str] = {
    EXAM_CATEGORY_PROPERTY_SCENE: "Local de furto, roubo ou dano",
    EXAM_CATEGORY_TRAFFIC_ACCIDENT: "Acidente de trânsito",
    EXAM_CATEGORY_WORK_ACCIDENT: "Acidente de trabalho",
    EXAM_CATEGORY_UNKNOWN: "Não identificado",
}

DEFERRED_MODULE_TODO_MESSAGES: dict[str, str] = {
    EXAM_CATEGORY_TRAFFIC_ACCIDENT: (
        "Módulo de acidente de trânsito será desenvolvido em breve."
    ),
    EXAM_CATEGORY_WORK_ACCIDENT: (
        "Módulo de acidente de trabalho será desenvolvido em breve."
    ),
}


def _fold_text(value: object) -> str:
    """Normaliza texto para comparação insensível a acentos e caixa."""
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    normalized = unicodedata.normalize("NFKD", cleaned)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _matches_any_pattern(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    """Indica se algum padrão regex casa com o texto informado."""
    return any(pattern.search(text) for pattern in patterns)


def infer_exam_category_from_text(*texts: object) -> str:
    """
    Infere categoria a partir de objetivo do exame, requisição ou orientações do perito.

    Complementa a IA quando ``exam_category`` permanece ``unknown`` apesar de haver
    indícios explícitos no texto — por exemplo, ``LEVANTAMENTO DE LOCAL - FURTO A RESIDENCIA``.
    """
    combined = " ".join(folded for item in texts if (folded := _fold_text(item)))
    if not combined:
        return EXAM_CATEGORY_UNKNOWN

    if _matches_any_pattern(combined, PROPERTY_SCENE_TEXT_PATTERNS):
        return EXAM_CATEGORY_PROPERTY_SCENE
    if _matches_any_pattern(combined, TRAFFIC_ACCIDENT_TEXT_PATTERNS):
        return EXAM_CATEGORY_TRAFFIC_ACCIDENT
    if _matches_any_pattern(combined, WORK_ACCIDENT_TEXT_PATTERNS):
        return EXAM_CATEGORY_WORK_ACCIDENT
    return EXAM_CATEGORY_UNKNOWN


def normalize_exam_category(value: object) -> str:
    """
    Normaliza categoria de exame vinda da IA, POST ou bootstrap.

    Valores desconhecidos ou vazios retornam ``unknown``.
    """
    cleaned = str(value or "").strip().lower()
    if cleaned in VALID_EXAM_CATEGORIES:
        return cleaned
    alias = EXAM_CATEGORY_ALIASES.get(cleaned.replace(" ", "_"))
    if alias:
        return alias
    return EXAM_CATEGORY_UNKNOWN


def is_property_scene_category(category: str) -> bool:
    """Indica se a categoria corresponde a exame de local patrimonial."""
    return normalize_exam_category(category) == EXAM_CATEGORY_PROPERTY_SCENE


def is_deferred_module_category(category: str) -> bool:
    """Indica categoria cujo módulo específico ainda será desenvolvido."""
    return normalize_exam_category(category) in DEFERRED_MODULE_CATEGORIES
