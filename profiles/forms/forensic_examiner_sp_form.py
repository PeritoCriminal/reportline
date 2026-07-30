"""
Formulário de edição do perfil profissional do servidor pericial (SP).

Permite que o usuário informe nome de exibição e cargo após o
administrador vincular sua conta a uma equipe pericial.
"""

from django import forms

from profiles.models import ForensicExaminerSP, ForensicJobTitle


class ForensicExaminerSPProfileForm(forms.ModelForm):
    """Campos editáveis pelo próprio servidor no perfil profissional."""

    job_title = forms.ChoiceField(
        choices=[("", "---------")] + list(ForensicJobTitle.choices),
        label="Cargo",
        help_text="Função exercida na equipe pericial.",
    )

    class Meta:
        model = ForensicExaminerSP
        fields = ("display_name", "job_title")
        labels = {
            "display_name": "Nome de exibição no laudo",
        }
        help_texts = {
            "display_name": (
                "Nome completo ou forma abreviada exibida na assinatura do laudo."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].required = True
        self.fields["job_title"].required = True
        self.fields["display_name"].widget.attrs.setdefault(
            "placeholder",
            "Ex.: Dr. João Silva",
        )
