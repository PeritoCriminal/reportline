"""
View de intake comum para geração de laudo pericial genérico.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from common.user_messages import notify_success
from institution_ic_sp.forensic_report.common.forms.case_intake_form import CaseIntakeForm
from institution_ic_sp.forensic_report.mixins import ForensicExaminerSPRequiredMixin
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW
from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell
from institution_ic_sp.forensic_report.workflows.initial_data.services.report_draft_builder import (
    build_generic_forensic_report_draft,
)


class CaseIntakeQuickShellView(ForensicExaminerSPRequiredMixin, View):
    """
    Cria casca de laudo pericial para bootstrap interativo no editor.

    Responde JSON com URLs de análise e montagem; não processa documentos.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        """Persiste laudo vazio com cabeçalho institucional e metadados iniciais."""
        supplementary_prompt = (request.POST.get("supplementary_prompt") or "").strip()
        report = create_forensic_report_shell(
            author=request.user,
            examiner=self.examiner_profile,
            supplementary_prompt=supplementary_prompt,
        )
        return JsonResponse(
            {
                "report_id": str(report.pk),
                "edit_url": reverse("reports:edit", kwargs={"pk": report.pk}),
                "analyze_url": reverse(
                    "reports:forensic_bootstrap_analyze",
                    kwargs={"pk": report.pk},
                ),
                "build_url": reverse(
                    "reports:forensic_bootstrap_build",
                    kwargs={"pk": report.pk},
                ),
            }
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
        context["analyze_documents_url"] = reverse(
            "institution_ic_sp:forensic_report:analyze_documents",
        )
        context["quick_shell_url"] = reverse(
            "institution_ic_sp:forensic_report:quick_shell",
        )
        return context

    def form_valid(self, form):
        """Processa intake revisado pelo perito, gera laudo e redireciona ao editor."""
        metadata = form.to_case_metadata()
        report = build_generic_forensic_report_draft(
            author=self.request.user,
            examiner=self.examiner_profile,
            metadata=metadata,
        )

        notify_success(self.request, "Laudo pericial criado com sucesso.")
        return HttpResponseRedirect(
            reverse("reports:edit", kwargs={"pk": report.pk}),
        )
