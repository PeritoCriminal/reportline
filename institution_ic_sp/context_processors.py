"""
Context processors do app institution_ic_sp.

Expõe flags de perfil pericial para templates globais.
"""


def forensic_examiner_context(request):
    """Indica se o usuário autenticado possui perfil ForensicExaminerSP."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"is_forensic_examiner_sp": False}
    return {
        "is_forensic_examiner_sp": hasattr(request.user, "forensic_examiner_sp"),
    }
