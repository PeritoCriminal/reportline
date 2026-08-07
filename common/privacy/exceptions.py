# reportline/common/privacy/exceptions.py
"""
Exceções do pipeline de sanitização para IA externa.
"""


class ExternalAiBlockedError(Exception):
    """Levantada quando o texto não pode ser enviado a provedor externo de IA."""

    def __init__(self, message: str = ""):
        default = (
            "Análise indisponível: o conteúdo contém dados sensíveis que "
            "não podem ser enviados a serviços externos."
        )
        super().__init__(message or default)
