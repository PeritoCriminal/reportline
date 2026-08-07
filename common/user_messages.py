# reportline/common/user_messages.py
"""
API centralizada de mensagens flash ao usuário do ReportLine.

Encapsula django.contrib.messages para garantir níveis semânticos consistentes
e um único ponto de evolução (tags extras, duração, ícones).
"""

from django.contrib import messages


def notify_success(request, text: str) -> None:
    """Registra mensagem de sucesso exibida como toast temporário."""
    messages.success(request, text)


def notify_error(request, text: str) -> None:
    """Registra mensagem de erro exibida como toast temporário."""
    messages.error(request, text)


def notify_warning(request, text: str) -> None:
    """Registra mensagem de alerta exibida como toast temporário."""
    messages.warning(request, text)


def notify_info(request, text: str) -> None:
    """Registra mensagem informativa exibida como toast temporário."""
    messages.info(request, text)
