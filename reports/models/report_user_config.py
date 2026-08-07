# reportline/reports/models/report_user_config.py
"""
Preferências padrão de editor de laudos por usuário.

Armazena opções aplicadas automaticamente a laudos novos; cada laudo
mantém cópia própria dos campos equivalentes no model ``Report``.
"""

from django.conf import settings
from django.db import models

from common.models import BaseModel


class ReportUserConfig(BaseModel):
    """
    Configuração padrão de laudos para um usuário autenticado.

    Relacionamento 1:1 com ``User``; valores são copiados para ``Report``
    na criação de novos documentos e atualizados quando o usuário salva
    configurações no editor.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="report_user_config",
        verbose_name="Usuário",
    )
    number_headings = models.BooleanField(
        default=True,
        verbose_name="Numerar títulos",
    )
    number_captions = models.BooleanField(
        default=False,
        verbose_name="Numerar legendas",
    )
    first_line_indent = models.BooleanField(
        default=True,
        verbose_name="Recuar primeira linha",
    )
    personal_page_layout = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Layout de página pessoal",
        help_text=(
            "Último cabeçalho e rodapé de relatórios comuns editados pelo usuário, "
            "aplicados a novos relatórios pessoais."
        ),
    )
    institutional_page_layout = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Layout de página institucional",
        help_text=(
            "Último cabeçalho e rodapé de laudos periciais editados pelo usuário, "
            "aplicados a novos laudos institucionais."
        ),
    )

    class Meta:
        verbose_name = "Configuração de laudo do usuário"
        verbose_name_plural = "Configurações de laudo dos usuários"

    def __str__(self):
        return f"Configuração de laudo — {self.user}"
