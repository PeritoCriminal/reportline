"""
View de intake comum para geração de laudo pericial genérico.
"""

from __future__ import annotations

import uuid

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from common.user_messages import notify_success
from institution_ic_sp.forensic_report.common.forms.case_intake_form import CaseIntakeForm
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    extract_case_metadata,
)
from institution_ic_sp.forensic_report.common.services.temp_uploads import (
    clear_temp_uploads,
    store_temp_uploads,
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
    encaminha o perito ao editor visual do documento.
    """

    form_class = CaseIntakeForm
    template_name = "institution_ic_sp/forensic_report/common/case_intake.html"

    def get_context_data(self, **kwargs):
        """Inclui metadados do workflow genérico no template."""
        context = super().get_context_data(**kwargs)
        context["workflow"] = GENERIC_WORKFLOW
        context["examiner_profile"] = self.examiner_profile
        return context

    def form_valid(self, form):
        """Processa intake, gera laudo e redireciona ao editor."""
        session_key = self._temp_session_key()
        uploaded_files = self.request.FILES.getlist("documents")
        stored_paths = store_temp_uploads(session_key, uploaded_files)

        try:
            form_metadata = form.to_case_metadata(
                uploaded_file_names=[path.rsplit("/", 1)[-1] for path in stored_paths],
            )
            metadata = extract_case_metadata(
                form_data=form_metadata,
                uploaded_files=uploaded_files,
            )
            report = build_generic_forensic_report_draft(
                author=self.request.user,
                examiner=self.examiner_profile,
                metadata=metadata,
            )
        finally:
            clear_temp_uploads(session_key)

        notify_success(self.request, "Laudo pericial criado com sucesso.")
        return HttpResponseRedirect(
            reverse("reports:edit", kwargs={"pk": report.pk}),
        )

    def _temp_session_key(self) -> str:
        """Retorna chave estável de sessão para uploads transitórios."""
        if not self.request.session.session_key:
            self.request.session.create()
        return self.request.session.session_key or uuid.uuid4().hex
