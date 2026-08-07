# reportline/common/tests/test_user_messages.py
"""
Testes da API centralizada de mensagens flash do ReportLine.
"""

from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from common.user_messages import (
    notify_error,
    notify_info,
    notify_success,
    notify_warning,
)


def _build_request_with_messages():
    """Monta request de teste com sessão e storage de mensagens."""
    request = RequestFactory().get("/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


class UserMessagesTests(TestCase):
    """Testes das funções notify_* e mapeamento para níveis do Django."""

    def test_notify_success_registers_success_level(self):
        """Garante que notify_success registre mensagem no nível success."""
        request = _build_request_with_messages()
        notify_success(request, "Operação concluída.")

        stored = list(get_messages(request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Operação concluída.")
        self.assertIn("success", stored[0].tags)

    def test_notify_error_registers_error_level(self):
        """Garante que notify_error registre mensagem no nível error."""
        request = _build_request_with_messages()
        notify_error(request, "Falha ao salvar.")

        stored = list(get_messages(request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Falha ao salvar.")
        self.assertIn("error", stored[0].tags)

    def test_notify_warning_registers_warning_level(self):
        """Garante que notify_warning registre mensagem no nível warning."""
        request = _build_request_with_messages()
        notify_warning(request, "Atenção necessária.")

        stored = list(get_messages(request))
        self.assertEqual(len(stored), 1)
        self.assertIn("warning", stored[0].tags)

    def test_notify_info_registers_info_level(self):
        """Garante que notify_info registre mensagem no nível info."""
        request = _build_request_with_messages()
        notify_info(request, "Informação relevante.")

        stored = list(get_messages(request))
        self.assertEqual(len(stored), 1)
        self.assertIn("info", stored[0].tags)
