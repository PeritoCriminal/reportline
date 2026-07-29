"""
Model de usuário personalizado do app accounts.

Define CustomUser com chave primária UUID para o ecossistema ReportLine.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class AuthProvider(models.TextChoices):
    """Provedores de autenticação suportados pelo ReportLine."""

    LOCAL = "local", "Local"
    GOOGLE = "google", "Google"
    GOVBR = "govbr", "gov.br"


class CustomUser(AbstractUser):
    """
    Modelo de usuário personalizado do ecossistema ReportLine.

    Substitui a chave primária sequencial padrão (AutoIncrement ID) por um
    identificador global único (UUIDv4). Esta abordagem mitiga vulnerabilidades
    de IDOR (Insecure Direct Object Reference) em endpoints públicos e previne
    a exposição de métricas de volumetria do banco de dados na camada de apresentação.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    auth_provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.LOCAL,
        verbose_name="Provedor de autenticação",
    )
    external_subject = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Identificador externo (OAuth)",
        help_text="Valor estável do claim 'sub' retornado pelo provedor OAuth.",
    )

    class Meta:
        app_label = "accounts"
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        constraints = [
            models.UniqueConstraint(
                fields=["auth_provider", "external_subject"],
                condition=models.Q(external_subject__isnull=False),
                name="unique_external_subject_per_provider",
            ),
        ]

    def __str__(self):
        return self.username
