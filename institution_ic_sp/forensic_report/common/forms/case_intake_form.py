"""
Formulário de intake comum para laudos periciais.
"""

from __future__ import annotations

from datetime import date

from django import forms


class CaseIntakeForm(forms.Form):
    """
    Campos administrativos reunidos na etapa comum de todos os workflows.

    Documentos anexos são tratados separadamente via ``request.FILES``
    por não haver suporte nativo a múltiplos arquivos em um único campo.
    """

    report_number = forms.CharField(
        label="Número do laudo",
        max_length=50,
        help_text="Numeração sequencial do laudo, sem o ano.",
    )
    report_year = forms.IntegerField(
        label="Ano",
        min_value=2000,
        max_value=2100,
        initial=date.today().year,
    )
    service_protocol = forms.CharField(
        label="Protocolo de atendimento",
        max_length=100,
        required=False,
    )
    requester = forms.CharField(
        label="Solicitante",
        max_length=255,
        required=False,
    )
    case_type = forms.CharField(
        label="Tipo de caso",
        max_length=255,
        required=False,
    )
    bulletin_number = forms.CharField(
        label="Número do boletim de ocorrência",
        max_length=100,
        required=False,
    )
    exam_objective = forms.CharField(
        label="Objetivo do exame",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    supplementary_prompt = forms.CharField(
        label="Informações complementares",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text=(
            "Descreva o contexto do exame ou orientações adicionais. "
            "Será considerado na inferência futura por IA."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-control"
            if isinstance(field.widget, forms.Textarea):
                pass
            field.widget.attrs.setdefault("class", css_class)

    def to_case_metadata(self, *, uploaded_file_names: list[str] | None = None):
        """Converte dados validados em ``CaseMetadata``."""
        from institution_ic_sp.forensic_report.common.services.case_metadata import (
            CaseMetadata,
        )

        cleaned = self.cleaned_data
        return CaseMetadata(
            report_number=cleaned["report_number"],
            report_year=cleaned["report_year"],
            service_protocol=cleaned.get("service_protocol", ""),
            requester=cleaned.get("requester", ""),
            case_type=cleaned.get("case_type", ""),
            bulletin_number=cleaned.get("bulletin_number", ""),
            exam_objective=cleaned.get("exam_objective", ""),
            supplementary_prompt=cleaned.get("supplementary_prompt", ""),
            uploaded_file_names=uploaded_file_names or [],
        )
