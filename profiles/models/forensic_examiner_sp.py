"""
Model de perfil do perito criminalístico de SP.

Vincula o usuário autenticado à lotação em equipe pericial e ao nome
exibido nos laudos produzidos no ReportLine.
"""

from django.conf import settings
from django.db import models

from common.models import BaseModel


class ForensicExaminerSP(BaseModel):
    """
    Perfil profissional do perito criminal de São Paulo.

    Cada CustomUser possui no máximo um perfil deste tipo. A lotação
    referencia uma ForensicTeam do app institution_ic_sp (relação N:1).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forensic_examiner_sp",
        verbose_name="Usuário",
    )
    display_name = models.CharField(
        max_length=255,
        verbose_name="Nome de exibição no laudo",
        help_text="Nome completo ou forma abreviada exibida na assinatura do laudo.",
    )
    forensic_team = models.ForeignKey(
        "institution_ic_sp.ForensicTeam",
        on_delete=models.PROTECT,
        related_name="examiners",
        verbose_name="Equipe pericial",
        help_text="Equipe de perícias criminalísticas à qual o perito está lotado.",
    )

    class Meta:
        verbose_name = "Perito criminal (SP)"
        verbose_name_plural = "Peritos criminais (SP)"
        ordering = ["display_name"]

    def __str__(self):
        return self.display_name
