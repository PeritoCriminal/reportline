"""
Rotas HTTP do app accounts.

Agrupa endpoints de autenticação e gestão de perfil de usuário.
"""

from django.urls import path

from accounts.views.auth_views import LoginView

app_name = "accounts"

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
]
