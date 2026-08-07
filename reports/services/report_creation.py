# reportline/reports/services/report_creation.py
"""
Serviço de criação de relatórios modulares.

Centraliza a persistência inicial de um relatório em rascunho
para reutilização em views, testes e futuras APIs.
"""

from django.contrib.auth.models import AbstractBaseUser

from reports.models import Report, ReportStatus
from reports.services.report_user_config import apply_user_defaults_to_report


def create_report(*, author: AbstractBaseUser, title: str) -> Report:
    """
    Cria relatório em rascunho vinculado ao autor informado.

    O snapshot textual do autor é preenchido automaticamente pelo ``save()``
    do model ``Report``. As preferências de editor do usuário são copiadas
    para o laudo recém-criado.
    """
    report = Report.objects.create(
        author=author,
        title=title.strip(),
        status=ReportStatus.DRAFT,
    )
    apply_user_defaults_to_report(report, author)
    return report
