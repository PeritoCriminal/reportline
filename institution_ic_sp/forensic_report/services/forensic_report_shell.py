# reportline/institution_ic_sp/forensic_report/services/forensic_report_shell.py
"""
Criação da casca inicial de laudo pericial para bootstrap interativo.

Persiste cabeçalho e rodapé institucionais sem corpo, aguardando análise
documental e montagem progressiva no editor.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    empty_bootstrap_payload,
)
from institution_ic_sp.forensic_report.services.institution_page_layout import (
    build_institution_page_layout,
)
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report
from reports.services.report_creation import create_report
from reports.services.report_user_page_layout import (
    merge_institutional_layout_with_user_preferences,
)


@transaction.atomic
def create_forensic_report_shell(
    *,
    author: AbstractBaseUser,
    examiner: ForensicExaminerSP,
    supplementary_prompt: str = "",
    workflow_slug: str = GENERIC_WORKFLOW.slug,
) -> Report:
    """
    Cria laudo pericial com faixas institucionais e metadados de bootstrap.

    O corpo permanece vazio até ``populate_forensic_report_body`` ser
    invocado após a análise documental.
    """
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    metadata = CaseMetadata(
        supplementary_prompt=supplementary_prompt.strip(),
        report_year=date.today().year,
        examiner=(examiner.display_name or "").strip(),
    )

    report = create_report(
        author=author,
        title=metadata.list_title,
        apply_page_layout=False,
    )
    fresh_layout = build_institution_page_layout(
        report,
        institution=institution,
        examiner=examiner,
        workflow=workflow_slug,
        main_title_text=metadata.header_report_number_text,
    )
    page_layout = merge_institutional_layout_with_user_preferences(
        report,
        author,
        fresh_layout,
    )
    bootstrap = empty_bootstrap_payload(supplementary_prompt=supplementary_prompt)
    bootstrap["metadata"]["examiner"] = metadata.examiner
    bootstrap["metadata"]["report_year"] = metadata.report_year
    report.page_layout = attach_bootstrap_meta(page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
