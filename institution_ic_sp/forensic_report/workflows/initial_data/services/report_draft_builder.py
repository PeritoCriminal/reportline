# reportline/institution_ic_sp/forensic_report/workflows/initial_data/services/report_draft_builder.py
"""
Montagem do rascunho inicial de laudo pericial genérico.

Cria ``Report`` com cabeçalho institucional e árvore de blocos
padronizada para edição imediata no editor de relatórios.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.registry import INITIAL_DATA_WORKFLOW
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    compute_pending_prompts,
    resolve_bootstrap_state,
    skipped_prompts_from_bootstrap,
)
from institution_ic_sp.forensic_report.services.forensic_report_body_builder import (
    populate_forensic_report_body,
)
from institution_ic_sp.forensic_report.services.institution_page_layout import (
    build_institution_page_layout,
)
from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report
from reports.services.report_creation import create_report


@transaction.atomic
def build_generic_forensic_report_draft(
    *,
    author: AbstractBaseUser,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
) -> Report:
    """
    Gera laudo pericial genérico em rascunho com estrutura padronizada.

    Persiste cabeçalho/rodapé institucionais, título principal, preâmbulo,
    seções administrativas e fechamento com campo de assinatura.
    """
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    report = create_report(author=author, title=metadata.list_title)

    page_layout = build_institution_page_layout(
        report,
        institution=institution,
        examiner=examiner,
        workflow=INITIAL_DATA_WORKFLOW.slug,
        main_title_text=metadata.header_report_number_text,
    )
    report.page_layout = page_layout
    report.save(update_fields=["page_layout", "updated_at"])

    nodes = populate_forensic_report_body(
        report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        replace_existing=False,
    )

    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    bootstrap = {
        "state": resolve_bootstrap_state(metadata, skipped=skipped),
        "workflow": INITIAL_DATA_WORKFLOW.slug,
        "metadata": case_metadata_to_form_dict(metadata),
        "nodes": nodes,
        "pending_prompts": compute_pending_prompts(metadata, skipped=skipped),
        "skipped_prompts": sorted(skipped),
    }
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])

    return report


@transaction.atomic
def build_forensic_report_from_bootstrap(
    report: Report,
    *,
    examiner: ForensicExaminerSP,
    metadata: CaseMetadata,
) -> Report:
    """Monta corpo do laudo a partir de metadados analisados no bootstrap."""
    institution = Institution.objects.first()
    if institution is None:
        raise ValueError("Instituição IC-SP não cadastrada.")

    nodes = populate_forensic_report_body(
        report,
        examiner=examiner,
        metadata=metadata,
        institution=institution,
        replace_existing=True,
    )

    skipped = skipped_prompts_from_bootstrap(report.page_layout)
    bootstrap = {
        "state": resolve_bootstrap_state(metadata, skipped=skipped),
        "workflow": INITIAL_DATA_WORKFLOW.slug,
        "metadata": case_metadata_to_form_dict(metadata),
        "nodes": nodes,
        "pending_prompts": compute_pending_prompts(metadata, skipped=skipped),
        "skipped_prompts": sorted(skipped),
    }
    report.page_layout = attach_bootstrap_meta(report.page_layout, bootstrap)
    report.save(update_fields=["page_layout", "updated_at"])
    return report
