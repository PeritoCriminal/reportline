# reportline/institution_ic_sp/forensic_report/common/forms/case_intake_form.py
"""
Formulário de intake comum para laudos periciais.
"""

from __future__ import annotations

from datetime import date

from django import forms

from institution_ic_sp.forensic_report.common.services.case_metadata import (
    UPPERCASE_TEXT_FIELDS,
    normalize_case_metadata,
)


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
    designation_date = forms.DateField(
        label="Data da designação",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    exam_objective = forms.CharField(
        label="Objetivo do exame",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    supplementary_prompt = forms.CharField(
        label="Informações complementares",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        help_text="Orientações do perito que prevalecem sobre os documentos analisados.",
    )
    requesting_authority = forms.CharField(
        label="Autoridade requisitante",
        max_length=512,
        required=False,
    )
    police_district = forms.CharField(
        label="Distrito policial / Delegacia",
        max_length=512,
        required=False,
    )
    occurrence_report = forms.CharField(
        label="Boletim de ocorrência",
        max_length=512,
        required=False,
    )
    police_inquiry = forms.CharField(
        label="Inquérito policial",
        max_length=512,
        required=False,
    )
    occurrence_at = forms.DateTimeField(
        label="Data e hora da ocorrência",
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    requisition_at = forms.DateTimeField(
        label="Data e hora da requisição",
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    attendance_protocol = forms.CharField(
        label="Número do protocolo",
        max_length=512,
        required=False,
    )
    examiner = forms.CharField(
        label="Perito",
        max_length=255,
        required=False,
    )
    examination_at = forms.DateTimeField(
        label="Data e hora do exame",
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"},
            format="%Y-%m-%dT%H:%M",
        ),
    )
    photography = forms.CharField(
        label="Fotógrafo",
        max_length=512,
        required=False,
    )
    scanning_3d = forms.CharField(
        label="Escaneamento 3D",
        max_length=512,
        required=False,
    )
    sketch = forms.CharField(
        label="Croqui",
        max_length=512,
        required=False,
    )

    def __init__(self, *args, examiner_display_name: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        datetime_local_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]
        for name in ("occurrence_at", "requisition_at", "examination_at"):
            self.fields[name].input_formats = datetime_local_formats

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.DateInput):
                continue
            css_class = field.widget.attrs.setdefault("class", "form-control")
            if name in UPPERCASE_TEXT_FIELDS:
                field.widget.attrs["class"] = f"{css_class} text-uppercase".strip()

        if examiner_display_name and not self.initial.get("examiner"):
            self.fields["examiner"].initial = examiner_display_name

    def to_case_metadata(self) -> "CaseMetadata":
        """Converte dados validados em ``CaseMetadata``."""
        from institution_ic_sp.forensic_report.common.services.case_metadata import (
            CaseMetadata,
        )

        cleaned = self.cleaned_data
        return normalize_case_metadata(
            CaseMetadata(
                report_number=cleaned["report_number"],
                report_year=cleaned["report_year"],
                designation_date=cleaned.get("designation_date"),
                exam_objective=cleaned.get("exam_objective", ""),
                supplementary_prompt=cleaned.get("supplementary_prompt", ""),
                requesting_authority=cleaned.get("requesting_authority", ""),
                police_district=cleaned.get("police_district", ""),
                occurrence_report=cleaned.get("occurrence_report", ""),
                police_inquiry=cleaned.get("police_inquiry", ""),
                occurrence_at=cleaned.get("occurrence_at"),
                requisition_at=cleaned.get("requisition_at"),
                attendance_protocol=cleaned.get("attendance_protocol", ""),
                examiner=cleaned.get("examiner", ""),
                examination_at=cleaned.get("examination_at"),
                photography=cleaned.get("photography", ""),
                scanning_3d=cleaned.get("scanning_3d", ""),
                sketch=cleaned.get("sketch", ""),
            )
        )
