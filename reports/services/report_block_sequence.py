# reportline/reports/services/report_block_sequence.py
"""
Regras de sequência de blocos no editor interativo.

Define qual tipo de bloco irmão deve ser criado após Enter,
conforme o tipo do bloco atual.
"""

from reports.models import ReportBlockType


def get_next_sibling_block_type(current_block_type: str) -> str:
    """
    Retorna o ``block_type`` do próximo nó irmão após Enter.

    Listas tratam Enter como novo item no mesmo nó — não usam esta função.
    """
    if current_block_type == ReportBlockType.HEADING:
        return ReportBlockType.PARAGRAPH
    if current_block_type == ReportBlockType.IMAGE:
        return ReportBlockType.PARAGRAPH
    return ReportBlockType.PARAGRAPH


def is_list_block_type(block_type: str) -> bool:
    """Indica se o tipo representa lista com itens no mesmo nó."""
    return block_type in (
        ReportBlockType.ORDERED_LIST,
        ReportBlockType.UNORDERED_LIST,
    )


def default_title_level_for_block_type(block_type: str) -> int:
    """Retorna nível hierárquico padrão ao criar bloco do tipo informado."""
    if block_type == ReportBlockType.HEADING:
        return 0
    return 0


def placeholder_for_block_type(block_type: str, *, is_caption: bool = False) -> str:
    """Texto placeholder exibido em blocos editáveis vazios."""
    if is_caption:
        return "Legenda da imagem"
    placeholders = {
        ReportBlockType.HEADING: "Título do relatório",
        ReportBlockType.PARAGRAPH: "Digite o parágrafo…",
        ReportBlockType.ORDERED_LIST: "Item da lista",
        ReportBlockType.UNORDERED_LIST: "Item da lista",
        ReportBlockType.LINK: "Texto do link",
        ReportBlockType.IMAGE: "Descrição da imagem",
    }
    return placeholders.get(block_type, "Digite aqui…")
