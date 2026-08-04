"""
Formulário de edição do perfil profissional do servidor pericial (SP).

Permite que o usuário informe nome de exibição, cargo, tratamento gramatical
e linha do diretor pericial após o administrador vincular a lotação.
"""

from django import forms

from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling
from profiles.services.forensic_examiner_sp_defaults import default_institution_director_display


class ForensicExaminerSPProfileForm(forms.ModelForm):
    """Campos editáveis pelo próprio servidor no perfil profissional."""

    job_title = forms.ChoiceField(
        choices=[("", "---------")] + list(ForensicJobTitle.choices),
        label="Cargo",
        help_text="Função exercida na equipe pericial.",
    )
    calling_gender = forms.ChoiceField(
        choices=[("", "---------")] + list(GenderCalling.choices),
        label="Tratamento gramatical",
        help_text="Usado na concordância de gênero do preâmbulo do laudo.",
    )

    class Meta:
        model = ForensicExaminerSP
        fields = ("display_name", "job_title", "calling_gender", "director_display")
        labels = {
            "display_name": "Nome de exibição no laudo",
            "director_display": "Diretor pericial (preâmbulo)",
        }
        help_texts = {
            "display_name": (
                "Nome completo ou forma abreviada exibida na assinatura do laudo."
            ),
            "director_display": (
                "Linha do Perito Criminal Diretor exibida no preâmbulo; "
                "padrão institucional sugerido abaixo."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].required = True
        self.fields["job_title"].required = True
        self.fields["calling_gender"].required = True
        self.fields["display_name"].widget.attrs.setdefault(
            "placeholder",
            "Ex.: Dr. João Silva",
        )
        if not self.instance.pk or not (self.instance.director_display or "").strip():
            self.fields["director_display"].initial = default_institution_director_display()
