"""
Views de autenticação do app accounts.

Concentra CBVs relacionadas a login, logout e fluxos de sessão
do ecossistema ReportLine.
"""

from django.http import HttpResponse
from django.views import View


class LoginView(View):
    """
    Placeholder da tela de login.

    Retorna resposta temporária enquanto o template e o fluxo
    completo de autenticação não forem implementados.
    """

    def get(self, request):
        """Exibe mensagem provisória de desenvolvimento da tela de login."""
        return HttpResponse("Tela de Login em desenvolvimento.")
