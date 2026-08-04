"""
Formulário administrativo do perfil ForensicExaminerSP.

Concentra a lotação em duas etapas: núcleo obrigatório na interface
e equipe opcional, restrita aos filhos do núcleo selecionado.
"""

from django import forms

from institution_ic_sp.models import ForensicNucleus, ForensicTeam
from profiles.models import ForensicExaminerSP
from profiles.services.forensic_examiner_sp_defaults import (
    default_institution_director_display,
)


class ForensicExaminerSPAdminForm(forms.ModelForm):
    """
    Formulário de lotação encadeada para o Django Admin.

    O campo ``lotacao_nucleus`` orienta a seleção na interface; na
    persistência, lotação direta no núcleo grava ``forensic_nucleus``,
    e lotação em equipe grava apenas ``forensic_team``.
    """

    lotacao_nucleus = forms.ModelChoiceField(
        queryset=ForensicNucleus.objects.order_by("sort_order", "name"),
        label="Núcleo pericial",
        help_text="Selecione primeiro o núcleo de lotação.",
        required=True,
    )

    class Meta:
        model = ForensicExaminerSP
        fields = (
            "user",
            "display_name",
            "job_title",
            "calling_gender",
            "director_display",
            "forensic_team",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["forensic_team"].required = False
        self.fields["forensic_team"].label = "Equipe pericial"
        self.fields["forensic_team"].help_text = (
            "Opcional. Deixe em branco se o servidor estiver lotado "
            "diretamente no núcleo."
        )
        self._configure_team_queryset()
        self._prefill_lotacao_nucleus()
        self._prefill_director_display()

    def _prefill_director_display(self):
        """Sugere linha do diretor institucional quando o perfil ainda não define valor."""
        if not (self.instance.director_display or "").strip():
            self.initial.setdefault(
                "director_display",
                default_institution_director_display(),
            )

    def _resolve_nucleus_id(self):
        """Obtém o núcleo informado no POST ou inferido da instância."""
        if self.data.get("lotacao_nucleus"):
            return self.data.get("lotacao_nucleus")
        assigned_nucleus = self.instance.assigned_nucleus
        if assigned_nucleus is not None:
            return str(assigned_nucleus.pk)
        return None

    def _configure_team_queryset(self):
        """Restringe equipes ao núcleo selecionado."""
        nucleus_id = self._resolve_nucleus_id()
        if nucleus_id:
            self.fields["forensic_team"].queryset = ForensicTeam.objects.filter(
                nucleus_id=nucleus_id,
            ).order_by("sort_order", "name")
        else:
            self.fields["forensic_team"].queryset = ForensicTeam.objects.none()

    def _prefill_lotacao_nucleus(self):
        """Preenche o núcleo ao editar lotação existente."""
        assigned_nucleus = self.instance.assigned_nucleus
        if assigned_nucleus is not None:
            self.initial.setdefault("lotacao_nucleus", assigned_nucleus.pk)

    def clean(self):
        """Valida coerência entre núcleo selecionado e equipe opcional."""
        cleaned_data = super().clean()
        nucleus = cleaned_data.get("lotacao_nucleus")
        team = cleaned_data.get("forensic_team")

        if team and nucleus and team.nucleus_id != nucleus.pk:
            self.add_error(
                "forensic_team",
                "A equipe deve pertencer ao núcleo selecionado.",
            )

        if not self.errors:
            self._apply_assignment_to_instance(
                nucleus=nucleus,
                team=team,
            )

        return cleaned_data

    def _apply_assignment_to_instance(self, *, nucleus, team):
        """Sincroniza a lotação da interface com a instância antes da validação do model."""
        if team:
            self.instance.forensic_team = team
            self.instance.forensic_nucleus = None
        else:
            self.instance.forensic_team = None
            self.instance.forensic_nucleus = nucleus

    def save(self, commit=True):
        """Traduz a lotação da interface para os campos persistidos no model."""
        instance = super().save(commit=False)
        self._apply_assignment_to_instance(
            nucleus=self.cleaned_data["lotacao_nucleus"],
            team=self.cleaned_data.get("forensic_team"),
        )

        if commit:
            instance.save()
            self.save_m2m()
        return instance
