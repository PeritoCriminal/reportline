"""
Testes do model CustomUser e regras de identificação.
"""

import uuid

from django.contrib.auth import get_user_model

from django.test import TestCase

CustomUser = get_user_model()


class CustomUserModelTests(TestCase):
    """Testes do model CustomUser."""

    def test_primary_key_is_uuid(self):
        """Garante que a chave primária seja UUID, não inteiro sequencial."""
        user = CustomUser.objects.create_user(
            username="perito1",
            password="senha-segura-123",
        )
        self.assertIsInstance(user.pk, uuid.UUID)

    def test_str_returns_username(self):
        """Garante representação textual baseada no username."""
        user = CustomUser.objects.create_user(
            username="perito_criminal",
            password="senha-segura-123",
        )
        self.assertEqual(str(user), "perito_criminal")

    def test_meta_verbose_names_in_portuguese(self):
        """Garante metadados de exibição em português na interface administrativa."""
        meta = CustomUser._meta
        self.assertEqual(meta.verbose_name, "Usuário")
        self.assertEqual(meta.verbose_name_plural, "Usuários")
