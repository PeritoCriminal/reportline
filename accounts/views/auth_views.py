"""
Views de autenticação do app accounts.

Concentra CBVs relacionadas a login, logout e fluxos de sessão
do ecossistema ReportLine.

Fase 0 (ADR-0003): login local Django username/senha.
Fase 1: Google OAuth em dev/deploy pessoal via django-allauth.
Fase 2 (futura): Login gov.br em ambiente institucional.
"""

from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.urls import reverse_lazy


class LoginView(DjangoLoginView):
    """
    Tela de login com credenciais locais Django.

    Destrava autenticação na fase de desenvolvimento até a integração
    OAuth (Google / gov.br) conforme ADR-0003.
    """

    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class LogoutView(DjangoLogoutView):
    """Encerra a sessão e redireciona para a tela de login."""

    next_page = reverse_lazy("accounts:login")
