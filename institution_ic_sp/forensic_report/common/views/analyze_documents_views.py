"""
View AJAX para análise documental e pré-preenchimento do intake comum.
"""

from __future__ import annotations

import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.views import View

from institution_ic_sp.forensic_report.common.ai.client import is_ai_configured
from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    analyze_case_metadata_from_documents,
)
from institution_ic_sp.forensic_report.common.services.case_metadata_serialization import (
    case_metadata_from_post,
    case_metadata_to_form_dict,
)
from institution_ic_sp.forensic_report.mixins import ForensicExaminerSPRequiredMixin
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW


class AnalyzeDocumentsView(ForensicExaminerSPRequiredMixin, View):
    """
    Lê documentos em memória e devolve metadados mesclados para o formulário.

    Não cria laudo nem persiste arquivos enviados.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        """Processa uploads e estado atual do formulário; responde JSON."""
        uploaded_files = request.FILES.getlist("documents")
        if not uploaded_files:
            return HttpResponseBadRequest(
                json.dumps({"error": "Selecione ao menos um documento para analisar."}),
                content_type="application/json",
            )

        manual = case_metadata_from_post(request.POST)
        document_excerpts = extract_text_from_uploads(uploaded_files)
        merged = analyze_case_metadata_from_documents(
            manual=manual,
            uploaded_files=uploaded_files,
            workflow_slug=GENERIC_WORKFLOW.slug,
        )

        warnings: list[str] = []
        if not document_excerpts:
            warnings.append(
                "Não foi possível extrair texto dos documentos enviados. "
                "Preencha os campos manualmente."
            )
        elif not is_ai_configured():
            warnings.append(
                "Serviço de IA indisponível. Configure OPENAI_API_KEY ou "
                "preencha os campos manualmente."
            )

        return JsonResponse(
            {
                "metadata": case_metadata_to_form_dict(merged),
                "warnings": warnings,
            }
        )
