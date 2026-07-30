"""
Model de relatório modular do ReportLine.

Representa um documento composto por uma árvore de nós, cada um vinculado
a um bloco genérico de conteúdo. Pertence ao usuário autor e suporta
evolução futura para laudos periciais e outros tipos de relatório.
"""

from django.conf import settings
from django.db import models

from common.models import BaseModel
from reports.services.author_snapshot import snapshot_author_fields


class ReportStatus(models.TextChoices):
    """Estados do ciclo de vida de um relatório."""

    DRAFT = "draft", "Rascunho"
    PUBLISHED = "published", "Publicado"
    ARCHIVED = "archived", "Arquivado"


class Report(BaseModel):
    """
    Relatório modular produzido por um usuário autenticado.

    A estrutura editável fica em ``ReportNode``; metadados de título e
    status permanecem neste model para listagens e controle de publicação.

    O vínculo com ``author`` é opcional após exclusão da conta: campos
    ``author_username`` e ``author_display_name`` preservam identificação
    textual para auditoria e exibição histórica do documento.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reports",
        null=True,
        blank=True,
        verbose_name="Autor",
        help_text="Desvinculado automaticamente quando a conta do autor é excluída.",
    )
    author_username = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Usuário do autor (snapshot)",
        help_text="Identificador textual preservado após exclusão da conta.",
    )
    author_display_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome do autor (snapshot)",
        help_text="Nome exibido preservado após exclusão da conta.",
    )
    title = models.CharField(
        max_length=255,
        verbose_name="Título",
    )
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.DRAFT,
        verbose_name="Status",
    )

    class Meta:
        verbose_name = "Relatório"
        verbose_name_plural = "Relatórios"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def author_label(self) -> str:
        """Retorna rótulo do autor ativo ou snapshot após desvinculação."""
        if self.author_id:
            name = self.author.get_full_name().strip()
            return name or self.author.get_username()
        if self.author_display_name:
            return self.author_display_name
        if self.author_username:
            return self.author_username
        return "Autor desconhecido"

    def save(self, *args, **kwargs):
        """Atualiza snapshot textual enquanto o autor estiver vinculado."""
        if self.author_id:
            snapshot = snapshot_author_fields(self.author)
            self.author_username = snapshot["author_username"]
            self.author_display_name = snapshot["author_display_name"]
        super().save(*args, **kwargs)
