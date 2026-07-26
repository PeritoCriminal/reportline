"""
Views de autenticação do app accounts.

Concentra CBVs relacionadas a login, logout e fluxos de sessão
do ecossistema ReportLine.

TODO(institucional): substituir autenticação local username/senha pelo Login
gov.br (OIDC) quando o ReportLine for implantado em ambiente institucional.
Ver docs/decisions/0003-govbr-authentication.md.
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
