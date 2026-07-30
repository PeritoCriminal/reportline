"""
Model de bloco genérico de conteúdo de relatório.

Armazena o tipo, opções de layout compartilhadas e o payload estruturado
de elementos reutilizáveis — títulos, parágrafos, listas, links, tabelas,
imagens — que compõem os nós de um relatório.
Tipos específicos de laudo pericial mapearão papéis semânticos (ex.: número
do laudo) sobre esses blocos genéricos.
"""

from django.core.validators import MaxValueValidator
from django.db import models

from common.models import BaseModel


class ReportBlockType(models.TextChoices):
    """Tipos genéricos de conteúdo suportados na composição de relatórios."""

    HEADING = "heading", "Título"
    PARAGRAPH = "paragraph", "Parágrafo"
    LINK = "link", "Link"
    ORDERED_LIST = "ordered_list", "Lista numerada"
    UNORDERED_LIST = "unordered_list", "Lista com marcadores"
    TABLE = "table", "Tabela"
    IMAGE = "image", "Imagem"


class ReportBlockLineSpacing(models.TextChoices):
    """Espaçamento vertical entre linhas do bloco na renderização."""

    COMPACT = "compact", "Diminuir espaçamento entre linhas"
    NORMAL = "normal", "Espaçamento padrão"
    RELAXED = "relaxed", "Aumentar espaçamento entre linhas"


class ReportBlock(BaseModel):
    """
    Bloco de conteúdo tipado associado a um nó de relatório.

    O campo ``content`` guarda o payload específico de cada ``block_type``,
    validado futuramente na camada de serviço ou formulário. Exemplos:
    título com ``title_level`` e texto em ``content``, parágrafo com corpo, itens de lista, URL de
    link, metadados de tabela ou referência de imagem.

    Opções de layout (paginação, recuo, espaçamento) aplicam-se a todos os
    tipos e serão interpretadas na camada de renderização do documento.
    """

    block_type = models.CharField(
        max_length=30,
        choices=ReportBlockType.choices,
        verbose_name="Tipo de bloco",
    )
    content = models.JSONField(
        default=dict,
        verbose_name="Conteúdo",
        help_text="Payload estruturado conforme o tipo de bloco.",
    )
    title_level = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(9)],
        verbose_name="Nível do título",
        help_text=(
            "Profundidade hierárquica do título (0 = mais alto). "
            "Usado na renderização de blocos do tipo título."
        ),
    )
    page_break_before = models.BooleanField(
        default=False,
        verbose_name="Quebrar página antes",
    )
    keep_with_previous = models.BooleanField(
        default=False,
        verbose_name="Manter com o anterior",
        help_text="Evita separação deste bloco do bloco imediatamente anterior.",
    )
    keep_with_next = models.BooleanField(
        default=False,
        verbose_name="Manter com o posterior",
        help_text="Evita separação deste bloco do bloco imediatamente posterior.",
    )
    indent_paragraph = models.BooleanField(
        default=False,
        verbose_name="Identar parágrafo",
    )
    first_line_indent = models.BooleanField(
        default=False,
        verbose_name="Recuar primeira linha",
    )
    line_spacing = models.CharField(
        max_length=10,
        choices=ReportBlockLineSpacing.choices,
        default=ReportBlockLineSpacing.NORMAL,
        verbose_name="Espaçamento entre linhas",
    )
    space_before = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(500)],
        verbose_name="Espaço antes",
        help_text="Espaço antes do bloco, em pontos tipográficos (pt).",
    )
    space_after = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(500)],
        verbose_name="Espaço após",
        help_text="Espaço após o bloco, em pontos tipográficos (pt).",
    )

    class Meta:
        verbose_name = "Bloco de relatório"
        verbose_name_plural = "Blocos de relatório"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_block_type_display()} ({self.pk})"
