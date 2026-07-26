"""
Model de núcleos periciais do IC-SP.

Agrupa unidades especializadas, regionais e de apoio conforme o Decreto
42.847/1998 e atualizações do organograma da SPTC.
"""

from django.db import models

from common.models import BaseModel


class ForensicNucleus(BaseModel):
    """
    Núcleo pericial do Instituto de Criminalística de São Paulo.

    Pode representar núcleos especializados (capital), núcleos regionais
    do interior ou unidades de apoio administrativo e logístico.
    """

    class NucleusType(models.TextChoices):
        SPECIALIZED = "specialized", "Especializado"
        FIELD_CAPITAL = "field_capital", "Perícia criminalística — capital e Grande SP"
        FIELD_INTERIOR = "field_interior", "Perícia criminalística — interior"
        SUPPORT = "support", "Apoio"

    class OrganizationalCenter(models.TextChoices):
        FORENSIC_EXPERTISE = "forensic_expertise", "Centro de Perícias"
        EXAMS_RESEARCH = "exams_research", "Centro de Exames, Análises e Pesquisas"
        LOGISTIC_SUPPORT = "logistic_support", "Núcleo de Apoio Logístico"
        ADMIN_SUPPORT = "admin_support", "Núcleo de Apoio Administrativo"

    institution = models.ForeignKey(
        "institution_ic_sp.Institution",
        on_delete=models.CASCADE,
        related_name="nuclei",
        verbose_name="Instituição",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código",
        help_text="Identificador institucional, ex.: NPC-CAP, IC-NAT.",
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nome",
    )
    nucleus_type = models.CharField(
        max_length=20,
        choices=NucleusType.choices,
        verbose_name="Tipo de núcleo",
    )
    organizational_center = models.CharField(
        max_length=30,
        choices=OrganizationalCenter.choices,
        verbose_name="Centro organizacional",
    )
    headquarters_city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Município-sede",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem de exibição",
    )

    class Meta:
        verbose_name = "Núcleo pericial"
        verbose_name_plural = "Núcleos periciais"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
