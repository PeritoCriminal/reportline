"""
Model de perfil do perito criminalístico de SP.

Vincula o usuário autenticado à lotação em equipe ou núcleo pericial,
ao cargo exercido e ao nome exibido nos laudos produzidos no ReportLine.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from common.models import BaseModel


class ForensicJobTitle(models.TextChoices):
    """Cargos periciais disponíveis no IC-SP para lotação operacional."""

    PERITO_CRIMINAL = "perito_criminal", "Perito Criminal"
    DESENHISTA_TECNICO = "desenhista_tecnico", "Desenhista Técnico Pericial"
    FOTOGRAFO_TECNICO = "fotografo_tecnico", "Fotógrafo Técnico Pericial"


class ForensicExaminerSP(BaseModel):
    """
    Perfil profissional do servidor pericial de São Paulo.

    Cada CustomUser possui no máximo um perfil deste tipo. A lotação
    referencia uma ForensicTeam ou, quando o servidor está lotado
    diretamente no núcleo, uma ForensicNucleus (relação N:1).
    O administrador vincula usuário e lotação; o próprio servidor
    completa nome de exibição e cargo pelo formulário de perfil.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forensic_examiner_sp",
        verbose_name="Usuário",
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome de exibição no laudo",
        help_text="Nome completo ou forma abreviada exibida na assinatura do laudo.",
    )
    job_title = models.CharField(
        max_length=30,
        choices=ForensicJobTitle.choices,
        blank=True,
        verbose_name="Cargo",
        help_text="Função exercida na lotação pericial.",
    )
    forensic_team = models.ForeignKey(
        "institution_ic_sp.ForensicTeam",
        on_delete=models.PROTECT,
        related_name="examiners",
        null=True,
        blank=True,
        verbose_name="Equipe pericial",
        help_text="Equipe de perícias criminalísticas à qual o servidor está lotado.",
    )
    forensic_nucleus = models.ForeignKey(
        "institution_ic_sp.ForensicNucleus",
        on_delete=models.PROTECT,
        related_name="direct_examiners",
        null=True,
        blank=True,
        verbose_name="Núcleo pericial",
        help_text=(
            "Use quando o servidor estiver lotado diretamente no núcleo, "
            "sem equipe pericial específica."
        ),
    )

    class Meta:
        verbose_name = "Perito criminal (SP)"
        verbose_name_plural = "Peritos criminais (SP)"
        ordering = ["display_name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        forensic_team__isnull=False,
                        forensic_nucleus__isnull=True,
                    )
                    | models.Q(
                        forensic_team__isnull=True,
                        forensic_nucleus__isnull=False,
                    )
                ),
                name="forensic_examiner_sp_exactly_one_assignment",
            ),
        ]

    def __str__(self):
        if self.display_name:
            return self.display_name
        return self.user.get_username()

    def clean(self):
        """Valida que a lotação seja exclusivamente em equipe ou em núcleo."""
        has_team = self.forensic_team_id is not None
        has_nucleus = self.forensic_nucleus_id is not None

        if has_team and has_nucleus:
            raise ValidationError(
                "Informe apenas a equipe pericial ou o núcleo pericial, não ambos."
            )
        if not has_team and not has_nucleus:
            raise ValidationError(
                "Informe a equipe pericial ou o núcleo pericial de lotação."
            )

    def save(self, *args, **kwargs):
        """Persiste o perfil após validar regras de lotação."""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_nucleus_direct_assignment(self) -> bool:
        """Indica lotação direta no núcleo, sem equipe pericial vinculada."""
        return self.forensic_nucleus_id is not None

    @property
    def assigned_nucleus(self):
        """Retorna o núcleo pericial da lotação, direto ou via equipe."""
        if self.forensic_nucleus_id is not None:
            return self.forensic_nucleus
        if self.forensic_team_id is not None:
            return self.forensic_team.nucleus
        return None

    @property
    def is_profile_complete(self) -> bool:
        """Indica se nome de exibição e cargo foram informados pelo servidor."""
        return bool(self.display_name and self.job_title)

    @property
    def has_full_institution_access(self) -> bool:
        """
        Indica acesso amplo às páginas do institution_ic_sp.

        Peritos criminais têm visão completa; desenhistas e fotógrafos
        terão escopo restrito quando as telas forem implementadas.
        """
        return self.job_title == ForensicJobTitle.PERITO_CRIMINAL
