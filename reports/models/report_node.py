# reportline/reports/models/report_node.py
"""
Model de nó na árvore de composição de um relatório.

Define posição hierárquica e ordem entre irmãos; cada nó referencia
exatamente um bloco genérico de conteúdo para renderização.
"""

from decimal import Decimal

from django.db import models

from common.models import BaseModel

from .report import Report
from .report_block import ReportBlock


class ReportNode(BaseModel):
    """
    Nó da árvore de um relatório.

    Nós raiz possuem ``parent`` nulo. A ordem entre irmãos usa
    ``position`` com indexação fracionária (Decimal) para permitir
    reordenação sem renumerar toda a sequência.
    """

    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="nodes",
        verbose_name="Relatório",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name="Nó pai",
        help_text="Nulo para nós na raiz do relatório.",
    )
    block = models.OneToOneField(
        ReportBlock,
        on_delete=models.CASCADE,
        related_name="node",
        verbose_name="Bloco de conteúdo",
    )
    position = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        default=Decimal("0"),
        verbose_name="Posição",
        help_text="Ordem entre nós irmãos; valores decimais permitem inserção flexível.",
    )

    class Meta:
        verbose_name = "Nó de relatório"
        verbose_name_plural = "Nós de relatório"
        ordering = ["position"]
        indexes = [
            models.Index(
                fields=["report", "parent", "position"],
                name="reports_node_tree_order_idx",
            ),
        ]

    def __str__(self):
        return f"Nó {self.pk} — {self.report.title}"
