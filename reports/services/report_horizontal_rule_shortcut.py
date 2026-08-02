"""
Atalho de teclado para inserir linha horizontal no editor.

Reconhece linhas compostas exclusivamente por underscores (três ou mais),
sem prefixo de espaço ou outro caractere.
"""

from __future__ import annotations

import re

HORIZONTAL_RULE_LINE_PATTERN = re.compile(r"^_{3,}$")


def is_horizontal_rule_shortcut_line(line_text: str) -> bool:
    """
    Indica se a linha corresponde ao atalho ``___`` + Enter.

    Retorna falso quando há qualquer caractere antes dos underscores na mesma linha.
    """
    if not isinstance(line_text, str):
        return False
    return bool(HORIZONTAL_RULE_LINE_PATTERN.match(line_text))
