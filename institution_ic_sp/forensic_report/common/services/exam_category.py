"""
Categorias de exame pericial inferidas ou escolhidas no intake.
"""

from __future__ import annotations

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


def normalize_exam_category(value: object) -> str:
    """
    Normaliza categoria de exame vinda da IA, POST ou bootstrap.

    Valores desconhecidos ou vazios retornam ``unknown``.
    """
    cleaned = str(value or "").strip().lower()
    if cleaned in VALID_EXAM_CATEGORIES:
        return cleaned
    return EXAM_CATEGORY_UNKNOWN


def is_property_scene_category(category: str) -> bool:
    """Indica se a categoria corresponde a exame de local patrimonial."""
    return normalize_exam_category(category) == EXAM_CATEGORY_PROPERTY_SCENE


def is_deferred_module_category(category: str) -> bool:
    """Indica categoria cujo módulo específico ainda será desenvolvido."""
    return normalize_exam_category(category) in DEFERRED_MODULE_CATEGORIES
