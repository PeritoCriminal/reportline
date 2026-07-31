"""
Formulários de criação e edição de metadados de relatório.
"""

from django import forms

from reports.models import Report


class ReportCreateForm(forms.ModelForm):
    """Campos mínimos para iniciar um novo relatório modular."""

    class Meta:
        model = Report
        fields = ("title",)
        labels = {
            "title": "Título do relatório",
        }
        help_texts = {
            "title": "Nome provisório do documento; pode ser ajustado depois no editor.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True
        self.fields["title"].widget.attrs.setdefault(
            "placeholder",
            "Ex.: Laudo pericial nº 123/2026",
        )
