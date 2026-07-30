"""
Model de equipes de perícias criminalísticas do IC-SP.

Representa as EPCs subordinadas aos núcleos regionais de perícia
criminalística e às equipes de apoio logístico.
"""

from django.db import models

from common.models import BaseModel


class ForensicTeam(BaseModel):
    """
    Equipe de perícias criminalísticas ou equipe técnica de apoio.

    Equipes regionais atendem municípios conforme delimitação da SPTC.
    Equipes embutidas (DEIC, DHPP, DETRAN) atuam junto a órgãos parceiros.
    """

    nucleus = models.ForeignKey(
        "institution_ic_sp.ForensicNucleus",
        on_delete=models.CASCADE,
        related_name="teams",
        verbose_name="Núcleo",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Código",
        help_text="Identificador institucional, ex.: EPC-SPC, EPC-GRU.",
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nome",
    )
    headquarters_city = models.CharField(
        max_length=100,
        verbose_name="Município-sede",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Telefone",
        help_text="Telefone institucional de contato da equipe.",
    )
    institutional_email = models.EmailField(
        blank=True,
        verbose_name="E-mail institucional",
        help_text="Endereço de e-mail oficial da equipe pericial.",
    )
    address = models.TextField(
        blank=True,
        verbose_name="Endereço",
        help_text="Endereço físico ou referência de localização da sede.",
    )
    is_embedded_unit = models.BooleanField(
        default=False,
        verbose_name="Unidade embutida",
        help_text=(
            "Equipe que exerce atividades junto a órgão parceiro "
            "(ex.: DHPP, DEIC, DETRAN)."
        ),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem de exibição",
    )

    class Meta:
        verbose_name = "Equipe pericial"
        verbose_name_plural = "Equipes periciais"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
