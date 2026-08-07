"""
Testes de branding e templates do Django Admin do ReportLine.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ReportLineAdminSiteTests(TestCase):
    """Testes da identidade visual e textos do painel administrativo."""

    def test_admin_site_branding_constants(self):
        """Garante títulos administrativos alinhados ao ReportLine."""
        self.assertEqual(admin.site.site_header, "Administração do Sistema ReportLine")
        self.assertEqual(admin.site.site_title, "ReportLine")
        self.assertEqual(admin.site.index_title, "Painel administrativo")

    def test_admin_login_page_renders_reportline_branding(self):
        """Garante textos e assets customizados na tela de login do admin."""
        response = self.client.get(reverse("admin:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administração do Sistema ReportLine")
        self.assertContains(response, "Entrar no painel administrativo")
        self.assertContains(response, "Voltar ao ReportLine")
        self.assertContains(response, "reportline_admin.css")

    def test_admin_index_renders_custom_header_for_superuser(self):
        """Garante cabeçalho customizado no índice administrativo autenticado."""
        user_model = get_user_model()
        admin_user = user_model.objects.create_superuser(
            username="admin_branding",
            email="admin_branding@example.com",
            password="senha-segura-admin",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administração do Sistema ReportLine")
        self.assertContains(response, "Painel administrativo")
        self.assertContains(response, "Ver o site")
        self.assertContains(response, "Sair")
