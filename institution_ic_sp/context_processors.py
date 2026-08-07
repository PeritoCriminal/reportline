# reportline/institution_ic_sp/context_processors.py
"""
Context processors do app institution_ic_sp.

Expõe flags de perfil pericial para templates globais.
"""

from django.urls import reverse

from reports.services.author_snapshot import snapshot_author_fields

INSTITUTION_HOME_LABEL = "SPTC"


def _home_new_report_options(user):
    """Monta opções do card Novo relatório na página inicial."""
    is_forensic = hasattr(user, "forensic_examiner_sp")
    author = snapshot_author_fields(user)
    options = []

    if is_forensic:
        options.append(
            {
                "kind": "institutional",
                "title": "Institucional",
                "subtitle": INSTITUTION_HOME_LABEL,
                "url": reverse("institution_ic_sp:forensic_report:intake"),
            }
        )

    options.append(
        {
            "kind": "common",
            "title": "Relatório Comum",
            "subtitle": author["author_display_name"],
            "url": reverse("reports:new"),
        }
    )
    return options


def forensic_examiner_context(request):
    """Indica se o usuário autenticado possui perfil ForensicExaminerSP."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "is_forensic_examiner_sp": False,
            "home_new_report_options": [],
        }
    is_forensic = hasattr(request.user, "forensic_examiner_sp")
    return {
        "is_forensic_examiner_sp": is_forensic,
        "home_new_report_options": _home_new_report_options(request.user),
    }
