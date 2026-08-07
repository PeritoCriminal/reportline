# reportline/common/models/base_model.py
"""
Model abstrato base do ReportLine.

Centraliza chave primária UUID e timestamps de auditoria de persistência
para models de domínio futuros.
"""

import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Model abstrato com PK UUID e timestamps de criação/atualização.

    Models de domínio (Profile, Report, Block, etc.) devem herdar desta
    classe. Não se aplica ao CustomUser, que estende AbstractUser com
    UUID próprio e migração já existente.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="Identificador",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    class Meta:
        abstract = True
