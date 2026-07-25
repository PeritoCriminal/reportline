"""
Pacote de views do app accounts.

Reexporta CBVs por domínio para facilitar imports internos.
"""

from .auth_views import LoginView

__all__ = ["LoginView"]
