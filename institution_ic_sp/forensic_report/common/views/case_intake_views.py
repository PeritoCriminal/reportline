"""
View de intake comum para geração de laudo pericial genérico.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from common.user_messages import notify_success
from institution_ic_sp.forensic_report.common.forms.case_intake_form import CaseIntakeForm
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    extract_case_metadata,
)
from institution_ic_sp.forensic_report.mixins import ForensicExaminerSPRequiredMixin
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.workflows.generic.services.report_draft_builder import (
    build_generic_forensic_report_draft,
)


class CaseIntakeView(ForensicExaminerSPRequiredMixin, FormView):
    """
    Formulário comum de laudo pericial com upload de documentos.

    Após validação, gera rascunho estruturado no app ``reports`` e
    encaminha o perito ao editor visual do documento. Documentos enviados
    são processados apenas em memória, sem persistência no servidor.
    """

    form_class = CaseIntakeForm
    template_name = "institution_ic_sp/forensic_report/common/case_intake.html"

    def get_form_kwargs(self):
        """Pré-preenche perito com nome de exibição do perfil vinculado."""
        kwargs = super().get_form_kwargs()
        kwargs["examiner_display_name"] = (self.examiner_profile.display_name or "").strip()
        return kwargs

    def get_context_data(self, **kwargs):
        """Inclui metadados do workflow genérico no template."""
        context = super().get_context_data(**kwargs)
        context["workflow"] = GENERIC_WORKFLOW
        context["examiner_profile"] = self.examiner_profile
        return context

    def form_valid(self, form):
        """Processa intake, gera laudo e redireciona ao editor."""
        uploaded_files = self.request.FILES.getlist("documents")
        form_metadata = form.to_case_metadata()
        metadata = extract_case_metadata(
            form_data=form_metadata,
            uploaded_files=uploaded_files,
        )
        report = build_generic_forensic_report_draft(
            author=self.request.user,
            examiner=self.examiner_profile,
            metadata=metadata,
        )

        notify_success(self.request, "Laudo pericial criado com sucesso.")
        return HttpResponseRedirect(
            reverse("reports:edit", kwargs={"pk": report.pk}),
        )
