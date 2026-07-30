"""
Utilitários de snapshot do autor em relatórios.

Desacopla metadados textuais do usuário para preservar rastreabilidade
quando a conta for excluída e o vínculo FK for removido.
"""


def snapshot_author_fields(user):
    """
    Extrai identificação textual do usuário para persistência no relatório.

    Retorna username e nome de exibição (nome completo ou username como fallback).
    """
    display_name = user.get_full_name().strip()
    return {
        "author_username": user.get_username(),
        "author_display_name": display_name or user.get_username(),
    }
