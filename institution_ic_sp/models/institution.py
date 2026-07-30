"""
Model da instituição pericial de referência do IC-SP.

Representa o Instituto de Criminalística de São Paulo enquanto fonte
provisória de dados organizacionais durante o desenvolvimento do ReportLine.
"""

from django.db import models

from common.file_fields import cleanup_replaced_files, delete_model_file_fields
from common.models import BaseModel


LOGO_FILE_FIELDS = ("sp_logo", "sptc_logo")


class Institution(BaseModel):
    """
    Instituição pericial de referência vinculada ao app institution_ic_sp.

    Mantém metadados do órgão cujos núcleos e equipes são espelhados
    localmente. Em ambiente institucional, este registro pode ser substituído
    por integração com cadastro oficial da SPTC.
    """

    name = models.CharField(
        max_length=255,
        verbose_name="Nome",
    )
    acronym = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Sigla",
    )
    parent_organization = models.CharField(
        max_length=255,
        verbose_name="Órgão superior",
        help_text="Unidade administrativa à qual a instituição está subordinada.",
    )
    legal_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Referência normativa",
        help_text="Ato legal ou normativo que define a estrutura organizacional.",
    )
    headquarters_city = models.CharField(
        max_length=100,
        verbose_name="Município-sede",
    )
    is_provisional = models.BooleanField(
        default=True,
        verbose_name="Cadastro provisório",
        help_text=(
            "Indica que os dados deste app são mantidos localmente e podem "
            "ser substituídos pelo equivalente institucional."
        ),
    )
    sp_logo = models.ImageField(
        upload_to="institution_ic_sp/logos/",
        blank=True,
        verbose_name="Logo do Estado de SP",
        help_text="Imagem exibida no cabeçalho do laudo (logo do Governo de SP).",
    )
    sptc_logo = models.ImageField(
        upload_to="institution_ic_sp/logos/",
        blank=True,
        verbose_name="Logo da SPTC",
        help_text="Imagem exibida no cabeçalho do laudo (logo da SPTC).",
    )

    class Meta:
        verbose_name = "Instituição"
        verbose_name_plural = "Instituições"
        ordering = ["name"]

    def __str__(self):
        return f"{self.acronym} — {self.name}"

    def save(self, *args, **kwargs):
        """
        Persiste a instituição e remove logos substituídos ou limpos do storage.
        """
        previous = None
        if self.pk:
            previous = Institution.objects.filter(pk=self.pk).first()

        super().save(*args, **kwargs)

        if previous is not None:
            cleanup_replaced_files(self, previous, LOGO_FILE_FIELDS)

    def delete(self, *args, **kwargs):
        """Exclui a instituição e remove arquivos de logo associados."""
        delete_model_file_fields(self, LOGO_FILE_FIELDS)
        super().delete(*args, **kwargs)
