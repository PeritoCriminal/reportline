"""
Testes da tag versioned_static.
"""

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings


class VersionedStaticTagTests(SimpleTestCase):
    """Testes de cache busting para arquivos estáticos em desenvolvimento."""

    @override_settings(DEBUG=True)
    def test_appends_version_query_when_debug_is_true(self):
        """Garante sufixo de versão na URL em modo DEBUG."""
        rendered = Template(
            "{% load versioned_static %}{% versioned_static 'reports/css/report_editor.css' %}"
        ).render(Context())

        self.assertIn("/static/reports/css/report_editor.css", rendered)
        self.assertRegex(rendered, r"[?&]v=\d+")

    @override_settings(DEBUG=False)
    def test_keeps_plain_url_when_debug_is_false(self):
        """Garante URL estática padrão fora do modo DEBUG."""
        rendered = Template(
            "{% load versioned_static %}{% versioned_static 'reports/css/report_editor.css' %}"
        ).render(Context())

        self.assertEqual(rendered, "/static/reports/css/report_editor.css")
