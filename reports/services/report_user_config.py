# reportline/reports/services/report_user_config.py
"""
Preferências padrão de laudo por usuário e cópia para novos relatórios.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from reports.models import Report, ReportUserConfig

DEFAULT_NUMBER_HEADINGS = True
DEFAULT_NUMBER_CAPTIONS = False
DEFAULT_FIRST_LINE_INDENT = True


def get_or_create_user_config(user: AbstractBaseUser) -> ReportUserConfig:
    """Retorna configuração do usuário, criando com defaults se necessário."""
    config, _created = ReportUserConfig.objects.get_or_create(
        user=user,
        defaults={
            "number_headings": DEFAULT_NUMBER_HEADINGS,
            "number_captions": DEFAULT_NUMBER_CAPTIONS,
            "first_line_indent": DEFAULT_FIRST_LINE_INDENT,
        },
    )
    return config


def apply_user_defaults_to_report(report: Report, user: AbstractBaseUser) -> Report:
    """Copia preferências do usuário para um laudo recém-criado."""
    config = get_or_create_user_config(user)
    report.number_headings = config.number_headings
    report.number_captions = config.number_captions
    report.first_line_indent = config.first_line_indent
    report.save(
        update_fields=[
            "number_headings",
            "number_captions",
            "first_line_indent",
            "updated_at",
        ]
    )
    from reports.services.report_user_page_layout import apply_user_page_layout_to_report

    apply_user_page_layout_to_report(report, user)
    return report


def serialize_report_config(report: Report) -> dict[str, bool]:
    """Serializa flags de configuração do laudo para API e templates."""
    return {
        "number_headings": report.number_headings,
        "number_captions": report.number_captions,
        "first_line_indent": report.first_line_indent,
    }
