"""
Valores padrão do perfil ForensicExaminerSP derivados da instituição IC-SP.
"""

from __future__ import annotations

from institution_ic_sp.models import Institution


def default_institution_director_display() -> str:
    """Retorna linha do diretor pericial cadastrada na instituição de referência."""
    institution = Institution.objects.first()
    if institution is None:
        return ""
    return (institution.director_display or "").strip()
